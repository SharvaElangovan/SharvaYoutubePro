use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;
use std::fs;
use std::path::PathBuf;
use std::process::Stdio;
use tauri::State;
use tokio::process::Command;

use crate::youtube::get_setting;

const VIDEO_GENERATOR_PATH: &str = "/home/sharva/projects/video generator";
const OUTPUT_PATH: &str = "/home/sharva/projects/video generator/output";

#[derive(Debug, Serialize, Deserialize)]
pub struct VideoFile {
    pub name: String,
    pub path: String,
    pub size: String,
    pub modified: String,
}

#[derive(Debug, Deserialize)]
pub struct GeneratorConfig {
    #[serde(rename = "type")]
    pub video_type: String,
    #[serde(rename = "numQuestions")]
    pub num_questions: Option<u32>,
    #[serde(rename = "questionTime")]
    pub question_time: Option<u32>,
    #[serde(rename = "answerTime")]
    pub answer_time: Option<u32>,
    #[serde(rename = "outputFilename")]
    pub output_filename: Option<String>,
}

fn format_file_size(bytes: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = KB * 1024;
    const GB: u64 = MB * 1024;

    if bytes >= GB {
        format!("{:.2} GB", bytes as f64 / GB as f64)
    } else if bytes >= MB {
        format!("{:.2} MB", bytes as f64 / MB as f64)
    } else if bytes >= KB {
        format!("{:.2} KB", bytes as f64 / KB as f64)
    } else {
        format!("{} B", bytes)
    }
}

fn format_timestamp(timestamp: std::time::SystemTime) -> String {
    use std::time::UNIX_EPOCH;

    let duration = timestamp.duration_since(UNIX_EPOCH).unwrap_or_default();
    let secs = duration.as_secs() as i64;

    // Simple date formatting
    let datetime = chrono::DateTime::from_timestamp(secs, 0)
        .unwrap_or_else(|| chrono::DateTime::from_timestamp(0, 0).unwrap());
    datetime.format("%Y-%m-%d %H:%M").to_string()
}

#[tauri::command]
pub async fn list_videos() -> Result<Vec<VideoFile>, String> {
    let output_dir = PathBuf::from(OUTPUT_PATH);

    if !output_dir.exists() {
        return Ok(vec![]);
    }

    let mut videos = Vec::new();

    let entries = fs::read_dir(&output_dir).map_err(|e| e.to_string())?;

    for entry in entries.flatten() {
        let path = entry.path();

        if path.extension().map_or(false, |ext| ext == "mp4") {
            if let Ok(metadata) = fs::metadata(&path) {
                let name = path.file_name()
                    .map(|n| n.to_string_lossy().to_string())
                    .unwrap_or_default();

                let size = format_file_size(metadata.len());
                let modified = metadata.modified()
                    .map(format_timestamp)
                    .unwrap_or_else(|_| "Unknown".to_string());

                videos.push(VideoFile {
                    name,
                    path: path.to_string_lossy().to_string(),
                    size,
                    modified,
                });
            }
        }
    }

    // Sort by modified time (newest first)
    videos.sort_by(|a, b| b.modified.cmp(&a.modified));

    Ok(videos)
}

#[tauri::command]
pub async fn generate_video(config: GeneratorConfig) -> Result<String, String> {
    let venv_python = format!("{}/venv/bin/python", VIDEO_GENERATOR_PATH);

    // Generate output filename
    let output_filename = config.output_filename
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| {
            let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S");
            format!("{}_{}.mp4", config.video_type, timestamp)
        });

    // Ensure filename ends with .mp4
    let output_filename = if output_filename.ends_with(".mp4") {
        output_filename
    } else {
        format!("{}.mp4", output_filename)
    };

    let output_path = format!("{}/{}", OUTPUT_PATH, output_filename);

    // Create a Python script to generate the video programmatically
    let python_script = match config.video_type.as_str() {
        "general_knowledge" => {
            let num_q = config.num_questions.unwrap_or(100);
            let q_time = config.question_time.unwrap_or(5);
            let a_time = config.answer_time.unwrap_or(3);

            // Fetch UNUSED questions from our SQLite database and mark them as used
            format!(r#"
import sys
import sqlite3
sys.path.insert(0, '{}')
from generators import GeneralKnowledgeGenerator

# Connect to our question database
db_path = '/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Fetch UNUSED questions (times_used = 0), prioritize them
cursor.execute('''
    SELECT id, question, option_a, option_b, option_c, option_d, correct_answer
    FROM question_bank
    WHERE times_used = 0
    ORDER BY RANDOM()
    LIMIT {}
''')
rows = cursor.fetchall()

# If not enough unused, get some used ones too
if len(rows) < {}:
    cursor.execute('''
        SELECT id, question, option_a, option_b, option_c, option_d, correct_answer
        FROM question_bank
        WHERE times_used > 0
        ORDER BY times_used ASC, RANDOM()
        LIMIT {}
    ''', ({} - len(rows),))
    rows.extend(cursor.fetchall())

# Mark these questions as used
question_ids = [row[0] for row in rows]
if question_ids:
    placeholders = ','.join('?' * len(question_ids))
    cursor.execute(f'''
        UPDATE question_bank
        SET times_used = times_used + 1
        WHERE id IN ({{placeholders}})
    ''', question_ids)
    conn.commit()

conn.close()

# Convert to generator format
questions = []
for row in rows:
    q_id, q_text, opt_a, opt_b, opt_c, opt_d, correct = row
    questions.append({{
        'question': q_text,
        'options': [opt_a, opt_b, opt_c, opt_d],
        'answer': correct
    }})

print(f'Loaded {{len(questions)}} questions (marked as used)')

generator = GeneralKnowledgeGenerator()
generator.question_time = {}
generator.answer_time = {}
output = generator.generate(questions, '{}')
print(output)
"#, VIDEO_GENERATOR_PATH, num_q, num_q, num_q, num_q, q_time, a_time, output_filename)
        },
        "spot_difference" => {
            format!(r#"
import sys
sys.path.insert(0, '{}')
from generators import SpotDifferenceGenerator

generator = SpotDifferenceGenerator()
output = generator.generate_auto(
    num_puzzles=5,
    num_differences=5,
    puzzle_time=10,
    reveal_time=5,
    output_filename='{}'
)
print(output)
"#, VIDEO_GENERATOR_PATH, output_filename)
        },
        "odd_one_out" => {
            format!(r#"
import sys
sys.path.insert(0, '{}')
from generators import OddOneOutGenerator

puzzles = []
diff_types = ['color', 'shape', 'size']
grids = [(3, 3), (4, 4), (4, 5), (5, 4)]

for i in range(5):
    puzzles.append({{
        'type': 'shape',
        'difference': diff_types[i % len(diff_types)],
        'grid': grids[i % len(grids)]
    }})

generator = OddOneOutGenerator()
output = generator.generate(
    puzzles,
    puzzle_time=8,
    answer_time=3,
    output_filename='{}'
)
print(output)
"#, VIDEO_GENERATOR_PATH, output_filename)
        },
        "emoji_word" => {
            format!(r#"
import sys
sys.path.insert(0, '{}')
from generators import EmojiWordGenerator
from generators.emoji_word import SAMPLE_EMOJI_PUZZLES

generator = EmojiWordGenerator()
output = generator.generate(
    SAMPLE_EMOJI_PUZZLES,
    guess_time=8,
    answer_time=3,
    output_filename='{}'
)
print(output)
"#, VIDEO_GENERATOR_PATH, output_filename)
        },
        _ => return Err(format!("Unknown video type: {}", config.video_type)),
    };

    // Run the Python script
    let output = Command::new(&venv_python)
        .arg("-c")
        .arg(&python_script)
        .current_dir(VIDEO_GENERATOR_PATH)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .await
        .map_err(|e| format!("Failed to run generator: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Generation failed: {}", stderr));
    }

    Ok(output_path)
}

#[tauri::command]
pub async fn delete_video(video_path: String) -> Result<(), String> {
    let path = PathBuf::from(&video_path);

    // Security check: ensure path is in output directory
    if !video_path.starts_with(OUTPUT_PATH) {
        return Err("Invalid video path".to_string());
    }

    fs::remove_file(&path).map_err(|e| format!("Failed to delete: {}", e))?;

    Ok(())
}

#[tauri::command]
pub async fn upload_to_youtube(
    pool: State<'_, SqlitePool>,
    video_path: String,
    title: String,
    description: String,
) -> Result<String, String> {
    let access_token = get_setting(&pool, "youtube_access_token")
        .await
        .ok_or("Not authenticated with YouTube. Please connect your account in Settings.")?;

    // Read the video file
    let video_data = fs::read(&video_path)
        .map_err(|e| format!("Failed to read video file: {}", e))?;

    let file_size = video_data.len();

    // Step 1: Initialize resumable upload
    let client = reqwest::Client::new();

    let metadata = serde_json::json!({
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22"  // People & Blogs
        },
        "status": {
            "privacyStatus": "private"  // Start as private for safety
        }
    });

    let init_response = client
        .post("https://www.googleapis.com/upload/youtube/v3/videos")
        .query(&[
            ("uploadType", "resumable"),
            ("part", "snippet,status"),
        ])
        .header("Authorization", format!("Bearer {}", access_token))
        .header("Content-Type", "application/json")
        .header("X-Upload-Content-Length", file_size.to_string())
        .header("X-Upload-Content-Type", "video/mp4")
        .json(&metadata)
        .send()
        .await
        .map_err(|e| format!("Failed to initialize upload: {}", e))?;

    if !init_response.status().is_success() {
        let error_text = init_response.text().await.unwrap_or_default();
        return Err(format!("YouTube API error: {}", error_text));
    }

    let upload_url = init_response
        .headers()
        .get("location")
        .ok_or("No upload URL returned")?
        .to_str()
        .map_err(|_| "Invalid upload URL")?
        .to_string();

    // Step 2: Upload the video
    let upload_response = client
        .put(&upload_url)
        .header("Content-Type", "video/mp4")
        .header("Content-Length", file_size.to_string())
        .body(video_data)
        .send()
        .await
        .map_err(|e| format!("Failed to upload video: {}", e))?;

    if !upload_response.status().is_success() {
        let error_text = upload_response.text().await.unwrap_or_default();
        return Err(format!("Upload failed: {}", error_text));
    }

    // Parse response to get video ID
    #[derive(Deserialize)]
    struct UploadResponse {
        id: String,
    }

    let response_data: UploadResponse = upload_response
        .json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    Ok(response_data.id)
}

#[derive(Debug, Clone, Serialize)]
pub struct AutomationStatus {
    pub running: bool,
    pub videos_generated: u32,
    pub videos_uploaded: u32,
    pub current_action: String,
    pub last_error: Option<String>,
}

use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Mutex;
use once_cell::sync::Lazy;

static AUTOMATION_RUNNING: AtomicBool = AtomicBool::new(false);
static VIDEOS_GENERATED: AtomicU32 = AtomicU32::new(0);
static VIDEOS_UPLOADED: AtomicU32 = AtomicU32::new(0);
static CURRENT_ACTION: Lazy<Mutex<String>> = Lazy::new(|| Mutex::new(String::new()));
static LAST_ERROR: Lazy<Mutex<Option<String>>> = Lazy::new(|| Mutex::new(None));
static GLOBAL_POOL: Lazy<Mutex<Option<SqlitePool>>> = Lazy::new(|| Mutex::new(None));

pub fn set_global_pool(pool: SqlitePool) {
    *GLOBAL_POOL.lock().unwrap() = Some(pool);
}

fn get_global_pool() -> Option<SqlitePool> {
    GLOBAL_POOL.lock().unwrap().clone()
}

#[tauri::command]
pub async fn get_automation_status() -> AutomationStatus {
    AutomationStatus {
        running: AUTOMATION_RUNNING.load(Ordering::SeqCst),
        videos_generated: VIDEOS_GENERATED.load(Ordering::SeqCst),
        videos_uploaded: VIDEOS_UPLOADED.load(Ordering::SeqCst),
        current_action: CURRENT_ACTION.lock().unwrap().clone(),
        last_error: LAST_ERROR.lock().unwrap().clone(),
    }
}

#[tauri::command]
pub async fn stop_automation() -> Result<(), String> {
    AUTOMATION_RUNNING.store(false, Ordering::SeqCst);
    *CURRENT_ACTION.lock().unwrap() = "Stopped".to_string();
    Ok(())
}

#[tauri::command]
pub async fn start_automation(
    config: GeneratorConfig,
    num_videos: u32,
) -> Result<String, String> {
    if AUTOMATION_RUNNING.load(Ordering::SeqCst) {
        return Err("Automation already running".to_string());
    }

    let pool_clone = get_global_pool()
        .ok_or("Database not initialized")?;

    AUTOMATION_RUNNING.store(true, Ordering::SeqCst);
    VIDEOS_GENERATED.store(0, Ordering::SeqCst);
    VIDEOS_UPLOADED.store(0, Ordering::SeqCst);
    *LAST_ERROR.lock().unwrap() = None;

    // Spawn automation task
    tokio::spawn(async move {
        for i in 1..=num_videos {
            if !AUTOMATION_RUNNING.load(Ordering::SeqCst) {
                break;
            }

            // Generate video
            *CURRENT_ACTION.lock().unwrap() = format!("Generating video {}/{}", i, num_videos);

            let gen_config = GeneratorConfig {
                video_type: config.video_type.clone(),
                num_questions: config.num_questions,
                question_time: config.question_time,
                answer_time: config.answer_time,
                output_filename: Some(format!("auto_quiz_{}.mp4", chrono::Local::now().format("%Y%m%d_%H%M%S"))),
            };

            match generate_video(gen_config).await {
                Ok(video_path) => {
                    VIDEOS_GENERATED.fetch_add(1, Ordering::SeqCst);

                    // Upload to YouTube
                    *CURRENT_ACTION.lock().unwrap() = format!("Uploading video {}/{}", i, num_videos);

                    let title = format!("Quiz #{} - Test Your Knowledge!", i);
                    let description = "General Knowledge Quiz - Can you get all questions right?\n\nSubscribe for more quizzes!\n\n#quiz #trivia #generalknowledge".to_string();

                    match upload_to_youtube_internal(&pool_clone, video_path.clone(), title, description).await {
                        Ok(video_id) => {
                            VIDEOS_UPLOADED.fetch_add(1, Ordering::SeqCst);
                            println!("Uploaded: https://youtube.com/watch?v={}", video_id);

                            // Delete local file after successful upload
                            let _ = fs::remove_file(&video_path);
                        }
                        Err(e) => {
                            *LAST_ERROR.lock().unwrap() = Some(format!("Upload failed: {}", e));
                            // Continue to next video even if upload fails
                        }
                    }
                }
                Err(e) => {
                    *LAST_ERROR.lock().unwrap() = Some(format!("Generation failed: {}", e));
                }
            }

            // Small delay between videos to avoid rate limiting
            if AUTOMATION_RUNNING.load(Ordering::SeqCst) && i < num_videos {
                tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
            }
        }

        AUTOMATION_RUNNING.store(false, Ordering::SeqCst);
        *CURRENT_ACTION.lock().unwrap() = "Completed".to_string();
    });

    Ok("Automation started".to_string())
}

async fn upload_to_youtube_internal(
    pool: &SqlitePool,
    video_path: String,
    title: String,
    description: String,
) -> Result<String, String> {
    let access_token = crate::youtube::get_setting_internal(pool, "youtube_access_token")
        .await
        .ok_or("Not authenticated with YouTube")?;

    let video_data = fs::read(&video_path)
        .map_err(|e| format!("Failed to read video: {}", e))?;

    let file_size = video_data.len();
    let client = reqwest::Client::new();

    let metadata = serde_json::json!({
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22",
            "tags": ["quiz", "trivia", "general knowledge", "brain teaser", "fun"]
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": false
        }
    });

    let init_response = client
        .post("https://www.googleapis.com/upload/youtube/v3/videos")
        .query(&[("uploadType", "resumable"), ("part", "snippet,status")])
        .header("Authorization", format!("Bearer {}", access_token))
        .header("Content-Type", "application/json")
        .header("X-Upload-Content-Length", file_size.to_string())
        .header("X-Upload-Content-Type", "video/mp4")
        .json(&metadata)
        .send()
        .await
        .map_err(|e| format!("Init failed: {}", e))?;

    if !init_response.status().is_success() {
        let error_text = init_response.text().await.unwrap_or_default();
        return Err(format!("YouTube API error: {}", error_text));
    }

    let upload_url = init_response
        .headers()
        .get("location")
        .ok_or("No upload URL")?
        .to_str()
        .map_err(|_| "Invalid URL")?
        .to_string();

    let upload_response = client
        .put(&upload_url)
        .header("Content-Type", "video/mp4")
        .header("Content-Length", file_size.to_string())
        .body(video_data)
        .send()
        .await
        .map_err(|e| format!("Upload failed: {}", e))?;

    if !upload_response.status().is_success() {
        let error_text = upload_response.text().await.unwrap_or_default();
        return Err(format!("Upload failed: {}", error_text));
    }

    #[derive(Deserialize)]
    struct UploadResponse { id: String }

    let response_data: UploadResponse = upload_response
        .json()
        .await
        .map_err(|e| format!("Parse failed: {}", e))?;

    Ok(response_data.id)
}
