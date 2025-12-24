use sqlx::{sqlite::SqlitePoolOptions, SqlitePool};
use std::fs;
use std::sync::Arc;
use tauri::Manager;
use tokio::sync::Mutex;

mod db;
mod questions;
mod videos;
mod youtube;

use youtube::{OAuthState, SharedOAuthState};

async fn init_database(app_data_dir: &std::path::Path) -> Result<SqlitePool, sqlx::Error> {
    fs::create_dir_all(app_data_dir).expect("Failed to create app data directory");

    let db_path = app_data_dir.join("sharva_youtube_pro.db");
    let db_url = format!("sqlite:{}?mode=rwc", db_path.display());

    let pool = SqlitePoolOptions::new()
        .max_connections(5)
        .connect(&db_url)
        .await?;

    // Run migrations
    db::run_migrations(&pool).await?;

    Ok(pool)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let app_data_dir = app
                .path()
                .app_data_dir()
                .expect("Failed to get app data directory");

            let handle = app.handle().clone();
            tauri::async_runtime::block_on(async move {
                match init_database(&app_data_dir).await {
                    Ok(pool) => {
                        // Set global pool for automation FIRST
                        videos::set_global_pool(pool.clone());
                        println!("Global pool set for automation");
                        handle.manage(pool);
                        handle.manage::<SharedOAuthState>(Arc::new(Mutex::new(OAuthState::default())));
                        println!("Database initialized successfully");
                        log::info!("Database initialized successfully");
                    }
                    Err(e) => {
                        println!("CRITICAL: Failed to initialize database: {}", e);
                        log::error!("Failed to initialize database: {}", e);
                        panic!("Database initialization failed: {}", e);
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            youtube::get_youtube_settings,
            youtube::save_youtube_settings,
            youtube::authenticate_youtube,
            youtube::disconnect_youtube,
            videos::list_videos,
            videos::generate_video,
            videos::delete_video,
            videos::upload_to_youtube,
            videos::start_automation,
            videos::stop_automation,
            videos::get_automation_status,
            questions::get_topics,
            questions::get_question_stats,
            questions::get_questions,
            questions::get_random_questions,
            questions::add_question,
            questions::add_questions_bulk,
            questions::delete_question,
            questions::add_topic,
            questions::increment_question_usage,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
