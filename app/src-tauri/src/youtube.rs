use oauth2::{
    basic::BasicClient, AuthUrl, AuthorizationCode, ClientId, ClientSecret, CsrfToken,
    PkceCodeChallenge, RedirectUrl, Scope, TokenResponse, TokenUrl,
};
use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;
use std::sync::Arc;
use tauri::State;
use tokio::sync::Mutex;

const GOOGLE_AUTH_URL: &str = "https://accounts.google.com/o/oauth2/v2/auth";
const GOOGLE_TOKEN_URL: &str = "https://oauth2.googleapis.com/token";
const REDIRECT_URI: &str = "http://localhost:8085/callback";

#[derive(Debug, Serialize, Deserialize)]
pub struct YouTubeSettings {
    pub client_id: String,
    pub client_secret: String,
    pub is_authenticated: bool,
    pub channel_name: Option<String>,
}

pub struct OAuthState {
    pub pkce_verifier: Option<oauth2::PkceCodeVerifier>,
    pub csrf_token: Option<CsrfToken>,
}

impl Default for OAuthState {
    fn default() -> Self {
        Self {
            pkce_verifier: None,
            csrf_token: None,
        }
    }
}

pub type SharedOAuthState = Arc<Mutex<OAuthState>>;

pub async fn get_setting(pool: &SqlitePool, key: &str) -> Option<String> {
    sqlx::query_scalar::<_, String>("SELECT value FROM settings WHERE key = ?")
        .bind(key)
        .fetch_optional(pool)
        .await
        .ok()
        .flatten()
}

pub async fn set_setting(pool: &SqlitePool, key: &str, value: &str) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
    )
    .bind(key)
    .bind(value)
    .bind(value)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn delete_setting(pool: &SqlitePool, key: &str) -> Result<(), sqlx::Error> {
    sqlx::query("DELETE FROM settings WHERE key = ?")
        .bind(key)
        .execute(pool)
        .await?;
    Ok(())
}

fn create_oauth_client(client_id: &str, client_secret: &str) -> Result<BasicClient, String> {
    let client = BasicClient::new(
        ClientId::new(client_id.to_string()),
        Some(ClientSecret::new(client_secret.to_string())),
        AuthUrl::new(GOOGLE_AUTH_URL.to_string()).map_err(|e| e.to_string())?,
        Some(TokenUrl::new(GOOGLE_TOKEN_URL.to_string()).map_err(|e| e.to_string())?),
    )
    .set_redirect_uri(RedirectUrl::new(REDIRECT_URI.to_string()).map_err(|e| e.to_string())?);

    Ok(client)
}

#[tauri::command]
pub async fn get_youtube_settings(
    pool: State<'_, SqlitePool>,
) -> Result<YouTubeSettings, String> {
    let client_id = get_setting(&pool, "youtube_client_id")
        .await
        .unwrap_or_default();
    let client_secret = get_setting(&pool, "youtube_client_secret")
        .await
        .unwrap_or_default();
    let access_token = get_setting(&pool, "youtube_access_token").await;
    let channel_name = get_setting(&pool, "youtube_channel_name").await;

    Ok(YouTubeSettings {
        client_id,
        client_secret,
        is_authenticated: access_token.is_some(),
        channel_name,
    })
}

#[tauri::command]
pub async fn save_youtube_settings(
    pool: State<'_, SqlitePool>,
    client_id: String,
    client_secret: String,
) -> Result<(), String> {
    set_setting(&pool, "youtube_client_id", &client_id)
        .await
        .map_err(|e| e.to_string())?;
    set_setting(&pool, "youtube_client_secret", &client_secret)
        .await
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub async fn authenticate_youtube(
    pool: State<'_, SqlitePool>,
    oauth_state: State<'_, SharedOAuthState>,
) -> Result<(), String> {
    let client_id = get_setting(&pool, "youtube_client_id")
        .await
        .ok_or("Client ID not configured")?;
    let client_secret = get_setting(&pool, "youtube_client_secret")
        .await
        .ok_or("Client Secret not configured")?;

    let client = create_oauth_client(&client_id, &client_secret)?;

    let (pkce_challenge, pkce_verifier) = PkceCodeChallenge::new_random_sha256();

    let (auth_url, csrf_token) = client
        .authorize_url(CsrfToken::new_random)
        .add_scope(Scope::new(
            "https://www.googleapis.com/auth/youtube.upload".to_string(),
        ))
        .add_scope(Scope::new(
            "https://www.googleapis.com/auth/youtube.readonly".to_string(),
        ))
        .set_pkce_challenge(pkce_challenge)
        .url();

    // Store the PKCE verifier and CSRF token for later use
    {
        let mut state = oauth_state.lock().await;
        state.pkce_verifier = Some(pkce_verifier);
        state.csrf_token = Some(csrf_token);
    }

    // Start local server to handle callback
    let pool_clone = pool.inner().clone();
    let oauth_state_clone = oauth_state.inner().clone();

    tokio::spawn(async move {
        if let Err(e) = start_oauth_callback_server(pool_clone, oauth_state_clone).await {
            log::error!("OAuth callback server error: {}", e);
        }
    });

    // Open browser for authentication
    let url_string = auth_url.to_string();
    open::that(&url_string).map_err(|e| e.to_string())?;

    Ok(())
}

async fn start_oauth_callback_server(
    pool: SqlitePool,
    oauth_state: SharedOAuthState,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
    use tokio::net::TcpListener;

    let listener = TcpListener::bind("127.0.0.1:8085").await?;
    log::info!("OAuth callback server listening on port 8085");

    let (mut socket, _) = listener.accept().await?;
    let (reader, mut writer) = socket.split();
    let mut buf_reader = BufReader::new(reader);
    let mut request_line = String::new();
    buf_reader.read_line(&mut request_line).await?;

    // Parse the authorization code from the request
    let code = request_line
        .split_whitespace()
        .nth(1)
        .and_then(|path| {
            path.split('?')
                .nth(1)
                .and_then(|query| {
                    query.split('&').find_map(|param| {
                        let mut parts = param.split('=');
                        if parts.next() == Some("code") {
                            parts.next().map(|s| s.to_string())
                        } else {
                            None
                        }
                    })
                })
        });

    let response = if let Some(code) = code {
        // Exchange code for token
        match exchange_code_for_token(&pool, &oauth_state, &code).await {
            Ok(_) => {
                log::info!("Successfully authenticated with YouTube");
                "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html><body><h1>Authentication Successful!</h1><p>You can close this window and return to SharvaYoutubePro.</p><script>setTimeout(() => window.close(), 2000);</script></body></html>"
            }
            Err(e) => {
                log::error!("Failed to exchange code: {}", e);
                "HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html\r\n\r\n<html><body><h1>Authentication Failed</h1><p>Please try again.</p></body></html>"
            }
        }
    } else {
        "HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n<html><body><h1>Invalid Request</h1></body></html>"
    };

    writer.write_all(response.as_bytes()).await?;
    writer.flush().await?;

    Ok(())
}

async fn exchange_code_for_token(
    pool: &SqlitePool,
    oauth_state: &SharedOAuthState,
    code: &str,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let client_id = get_setting(pool, "youtube_client_id")
        .await
        .ok_or("Client ID not found")?;
    let client_secret = get_setting(pool, "youtube_client_secret")
        .await
        .ok_or("Client Secret not found")?;

    let pkce_verifier = {
        let mut state = oauth_state.lock().await;
        state.pkce_verifier.take().ok_or("PKCE verifier not found")?
    };

    let client = create_oauth_client(&client_id, &client_secret)?;

    let token_result = client
        .exchange_code(AuthorizationCode::new(code.to_string()))
        .set_pkce_verifier(pkce_verifier)
        .request_async(oauth2::reqwest::async_http_client)
        .await?;

    let access_token = token_result.access_token().secret().to_string();
    let refresh_token = token_result
        .refresh_token()
        .map(|t| t.secret().to_string());

    // Save tokens
    set_setting(pool, "youtube_access_token", &access_token).await?;
    if let Some(ref rt) = refresh_token {
        set_setting(pool, "youtube_refresh_token", rt).await?;
    }

    // Fetch channel info
    if let Ok(channel_name) = fetch_channel_name(&access_token).await {
        set_setting(pool, "youtube_channel_name", &channel_name).await?;
    }

    Ok(())
}

async fn fetch_channel_name(access_token: &str) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
    let client = reqwest::Client::new();
    let response = client
        .get("https://www.googleapis.com/youtube/v3/channels")
        .query(&[("part", "snippet"), ("mine", "true")])
        .bearer_auth(access_token)
        .send()
        .await?;

    #[derive(Deserialize)]
    struct ChannelResponse {
        items: Vec<ChannelItem>,
    }

    #[derive(Deserialize)]
    struct ChannelItem {
        snippet: ChannelSnippet,
    }

    #[derive(Deserialize)]
    struct ChannelSnippet {
        title: String,
    }

    let data: ChannelResponse = response.json().await?;
    data.items
        .first()
        .map(|item| item.snippet.title.clone())
        .ok_or_else(|| "No channel found".into())
}

#[tauri::command]
pub async fn disconnect_youtube(pool: State<'_, SqlitePool>) -> Result<(), String> {
    delete_setting(&pool, "youtube_access_token")
        .await
        .map_err(|e| e.to_string())?;
    delete_setting(&pool, "youtube_refresh_token")
        .await
        .map_err(|e| e.to_string())?;
    delete_setting(&pool, "youtube_channel_name")
        .await
        .map_err(|e| e.to_string())?;
    Ok(())
}
