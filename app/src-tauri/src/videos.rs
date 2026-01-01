use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;
use std::fs;
use std::path::PathBuf;
use std::process::Stdio;
use tauri::State;
use tokio::process::Command;

use crate::youtube::get_setting;

const VIDEO_GENERATOR_PATH: &str = "/home/sharva/projects/SharvaYoutubePro/video_generator";
const OUTPUT_PATH: &str = "/home/sharva/projects/SharvaYoutubePro/video_generator/output";

#[derive(Debug, Serialize, Deserialize)]
pub struct VideoFile {
    pub name: String,
    pub path: String,
    pub size: String,
    pub modified: String,
}

#[derive(Debug, Deserialize, Clone)]
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
    #[serde(rename = "isShorts", default)]
    pub is_shorts: bool,
    #[serde(rename = "resolution", default)]
    pub resolution: Option<String>,
}

// SEO-optimized title templates for better YouTube visibility
const TITLE_TEMPLATES: &[&str] = &[
    "Can You Pass This Quiz? {} Questions",
    "Only 1% Can Answer All {} Questions",
    "Test Your Brain: {} Hard Questions",
    "IQ Test: {} Questions Only Geniuses Solve",
    "{} Quiz Questions That Will Blow Your Mind",
    "How Smart Are You? {} Question Challenge",
    "Brain Teaser: {} Questions to Test Your Knowledge",
    "Ultimate Quiz Challenge: {} Questions",
    "Are You Smarter Than Average? {} Questions",
    "Trivia Master: {} Question Challenge",
];

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
            let q_time = config.question_time.unwrap_or(10);
            let a_time = config.answer_time.unwrap_or(5);
            let is_4k = config.resolution.as_deref() == Some("4k");
            let (width, height) = if is_4k { (3840, 2160) } else { (1920, 1080) };

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

# Fetch UNUSED questions - very strict filters for quality
cursor.execute('''
    SELECT id, question, option_a, option_b, option_c, option_d, correct_answer
    FROM question_bank
    WHERE times_used = 0
    AND length(question) BETWEEN 20 AND 150
    AND length(option_a) BETWEEN 1 AND 80
    AND length(option_b) BETWEEN 1 AND 80
    AND length(option_c) BETWEEN 1 AND 80
    AND length(option_d) BETWEEN 1 AND 80
    AND question NOT LIKE '%[%]%'
    AND question NOT LIKE '%http%'
    AND question NOT LIKE '%<%'
    AND option_a NOT LIKE '%[%]%'
    AND option_a NOT LIKE '%Not applicable%'
    AND option_a NOT LIKE '%Unknown%'
    AND option_a NOT LIKE '%None of these%'
    AND option_a NOT LIKE 'A %'
    AND option_a NOT LIKE 'The %'
    AND option_a NOT LIKE '%Smith'
    AND option_b NOT LIKE '%Not applicable%'
    AND option_b NOT LIKE '%Unknown%'
    AND option_b NOT LIKE '%None of these%'
    AND option_b NOT LIKE 'A %'
    AND option_b NOT LIKE 'The %'
    AND option_b NOT LIKE '%Smith'
    AND option_c NOT LIKE '%Not applicable%'
    AND option_c NOT LIKE '%Unknown%'
    AND option_c NOT LIKE '%None of these%'
    AND option_c NOT LIKE 'A %'
    AND option_c NOT LIKE 'The %'
    AND option_c NOT LIKE '%Smith'
    AND option_d NOT LIKE '%Not applicable%'
    AND option_d NOT LIKE '%Unknown%'
    AND option_d NOT LIKE '%None of these%'
    AND option_d NOT LIKE 'A %'
    AND option_d NOT LIKE 'The %'
    AND option_d NOT LIKE '%Smith'
    AND question LIKE '%?%'
    AND source IN ('opentriviaqa', 'triviaapi', 'opentdb', 'millionaire', 'built-in', 'sciq', 'arc', 'openbookqa', 'mistral')
    ORDER BY RANDOM()
    LIMIT {}
''')
rows = cursor.fetchall()

# If not enough unused, get some used ones too (with same filters)
if len(rows) < {}:
    cursor.execute('''
        SELECT id, question, option_a, option_b, option_c, option_d, correct_answer
        FROM question_bank
        WHERE times_used > 0
        AND length(question) BETWEEN 20 AND 150
        AND length(option_a) BETWEEN 1 AND 80
        AND length(option_b) BETWEEN 1 AND 80
        AND length(option_c) BETWEEN 1 AND 80
        AND length(option_d) BETWEEN 1 AND 80
        AND question NOT LIKE '%[%]%'
        AND question NOT LIKE '%http%'
        AND question NOT LIKE '%<%'
        AND option_a NOT LIKE '%[%]%'
        AND option_a NOT LIKE '%Not applicable%'
        AND option_a NOT LIKE '%Unknown%'
        AND option_a NOT LIKE '%None of these%'
        AND option_a NOT LIKE 'A %'
        AND option_a NOT LIKE 'The %'
        AND option_a NOT LIKE '%Smith'
        AND option_b NOT LIKE '%Not applicable%'
        AND option_b NOT LIKE '%Unknown%'
        AND option_b NOT LIKE '%None of these%'
        AND option_b NOT LIKE 'A %'
        AND option_b NOT LIKE 'The %'
        AND option_b NOT LIKE '%Smith'
        AND option_c NOT LIKE '%Not applicable%'
        AND option_c NOT LIKE '%Unknown%'
        AND option_c NOT LIKE '%None of these%'
        AND option_c NOT LIKE 'A %'
        AND option_c NOT LIKE 'The %'
        AND option_c NOT LIKE '%Smith'
        AND option_d NOT LIKE '%Not applicable%'
        AND option_d NOT LIKE '%Unknown%'
        AND option_d NOT LIKE '%None of these%'
        AND option_d NOT LIKE 'A %'
        AND option_d NOT LIKE 'The %'
        AND option_d NOT LIKE '%Smith'
        AND question LIKE '%?%'
        AND source IN ('opentriviaqa', 'triviaapi', 'opentdb', 'millionaire', 'built-in', 'sciq', 'arc', 'openbookqa', 'mistral')
        ORDER BY times_used ASC, RANDOM()
        LIMIT {}
    ''', ({} - len(rows),))
    rows.extend(cursor.fetchall())

# Keep question IDs for marking as used AFTER successful generation
question_ids = [row[0] for row in rows]

# Convert to generator format
questions = []
for row in rows:
    q_id, q_text, opt_a, opt_b, opt_c, opt_d, correct = row
    questions.append({{
        'question': q_text,
        'options': [opt_a, opt_b, opt_c, opt_d],
        'answer': correct
    }})

print(f'Loaded {{len(questions)}} questions')

generator = GeneralKnowledgeGenerator(width={}, height={})
generator.question_time = {}
generator.answer_time = {}
output = generator.generate(questions, '{}', enable_tts=True)

# Only mark questions as used AFTER successful video generation
import os
if os.path.exists(output) and os.path.getsize(output) > 1000:
    if question_ids:
        placeholders = ','.join('?' * len(question_ids))
        cursor.execute(f'''
            UPDATE question_bank
            SET times_used = times_used + 1
            WHERE id IN ({{placeholders}})
        ''', question_ids)
        conn.commit()
    print(f'Marked {{len(question_ids)}} questions as used')

conn.close()

# Generate thumbnail
thumbnail_path = output.replace('.mp4', '_thumb.jpg')
first_q = questions[0]['question'] if questions else 'Quiz Time!'
generator.generate_thumbnail(first_q[:50], f'{{len(questions)}} Questions', thumbnail_path)
print(f'THUMBNAIL:{{thumbnail_path}}')
print(output)
"#, VIDEO_GENERATOR_PATH, num_q, num_q, num_q, num_q, width, height, q_time, a_time, output_filename)
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
        "shorts" => {
            let num_q = config.num_questions.unwrap_or(5).min(5); // Max 5 for Shorts

            format!(r#"
import sys
import sqlite3
sys.path.insert(0, '{}')
from generators import ShortsGenerator

# Connect to our question database
db_path = '/home/sharva/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Fetch UNUSED questions for Shorts - very strict filters
cursor.execute('''
    SELECT id, question, option_a, option_b, option_c, option_d, correct_answer
    FROM question_bank
    WHERE times_used = 0
    AND length(question) BETWEEN 20 AND 120
    AND length(option_a) BETWEEN 1 AND 50
    AND length(option_b) BETWEEN 1 AND 50
    AND length(option_c) BETWEEN 1 AND 50
    AND length(option_d) BETWEEN 1 AND 50
    AND question NOT LIKE '%[%]%'
    AND question NOT LIKE '%http%'
    AND question NOT LIKE '%<%'
    AND option_a NOT LIKE '%[%]%'
    AND option_a NOT LIKE '%Not applicable%'
    AND option_a NOT LIKE '%Unknown%'
    AND option_a NOT LIKE '%None of these%'
    AND option_a NOT LIKE 'A %'
    AND option_a NOT LIKE 'The %'
    AND option_a NOT LIKE '%Smith'
    AND option_b NOT LIKE '%Not applicable%'
    AND option_b NOT LIKE '%Unknown%'
    AND option_b NOT LIKE '%None of these%'
    AND option_b NOT LIKE 'A %'
    AND option_b NOT LIKE 'The %'
    AND option_b NOT LIKE '%Smith'
    AND option_c NOT LIKE '%Not applicable%'
    AND option_c NOT LIKE '%Unknown%'
    AND option_c NOT LIKE '%None of these%'
    AND option_c NOT LIKE 'A %'
    AND option_c NOT LIKE 'The %'
    AND option_c NOT LIKE '%Smith'
    AND option_d NOT LIKE '%Not applicable%'
    AND option_d NOT LIKE '%Unknown%'
    AND option_d NOT LIKE '%None of these%'
    AND option_d NOT LIKE 'A %'
    AND option_d NOT LIKE 'The %'
    AND option_d NOT LIKE '%Smith'
    AND question LIKE '%?%'
    AND source IN ('opentriviaqa', 'triviaapi', 'opentdb', 'millionaire', 'built-in', 'sciq', 'arc', 'openbookqa', 'mistral')
    ORDER BY RANDOM()
    LIMIT {}
''')
rows = cursor.fetchall()

# Keep question IDs for marking as used AFTER successful generation
question_ids = [row[0] for row in rows]

# Convert to generator format
questions = []
for row in rows:
    q_id, q_text, opt_a, opt_b, opt_c, opt_d, correct = row
    questions.append({{
        'question': q_text,
        'options': [opt_a, opt_b, opt_c, opt_d],
        'answer': correct
    }})

print(f'Generating Shorts with {{len(questions)}} questions')

generator = ShortsGenerator()
output = generator.generate(questions, '{}', enable_tts=True)

# Only mark questions as used AFTER successful video generation
import os
if os.path.exists(output) and os.path.getsize(output) > 1000:
    if question_ids:
        placeholders = ','.join('?' * len(question_ids))
        cursor.execute(f'''
            UPDATE question_bank
            SET times_used = times_used + 1
            WHERE id IN ({{placeholders}})
        ''', question_ids)
        conn.commit()
    print(f'Marked {{len(question_ids)}} questions as used')

conn.close()

# Generate thumbnail for Shorts
thumbnail_path = output.replace('.mp4', '_thumb.jpg')
first_q = questions[0]['question'] if questions else 'Quiz Time!'
generator.generate_thumbnail(first_q, thumbnail_path)
print(f'THUMBNAIL:{{thumbnail_path}}')
print(output)
"#, VIDEO_GENERATOR_PATH, num_q, output_filename)
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
    log::info!("Setting global pool for automation...");
    *GLOBAL_POOL.lock().unwrap() = Some(pool);
    log::info!("Global pool set successfully!");
}

fn get_global_pool() -> Option<SqlitePool> {
    let pool = GLOBAL_POOL.lock().unwrap().clone();
    log::info!("get_global_pool called, has_pool: {}", pool.is_some());
    pool
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

            let is_shorts = config.is_shorts;
            let num_q = config.num_questions.unwrap_or(if is_shorts { 5 } else { 10 });
            let prefix = if is_shorts { "short" } else { "auto_quiz" };

            let gen_config = GeneratorConfig {
                video_type: if is_shorts { "shorts".to_string() } else { config.video_type.clone() },
                num_questions: Some(num_q),
                question_time: config.question_time,
                answer_time: config.answer_time,
                output_filename: Some(format!("{}_{}.mp4", prefix, chrono::Local::now().format("%Y%m%d_%H%M%S"))),
                is_shorts,
                resolution: config.resolution.clone(),
            };

            match generate_video(gen_config).await {
                Ok(video_path) => {
                    VIDEOS_GENERATED.fetch_add(1, Ordering::SeqCst);

                    // Upload to YouTube
                    *CURRENT_ACTION.lock().unwrap() = format!("Uploading video {}/{}", i, num_videos);

                    // Use SEO-optimized title templates
                    let template_idx = (i as usize - 1) % TITLE_TEMPLATES.len();
                    let title = TITLE_TEMPLATES[template_idx].replace("{}", &num_q.to_string());

                    let shorts_tag = if is_shorts { " #shorts" } else { "" };
                    let description = format!(
                        "🧠 {} Question Quiz - Can you get them all right?\n\n\
                        👆 Subscribe for daily quizzes!\n\
                        💬 Comment your score below!\n\n\
                        #quiz #trivia #generalknowledge #brainteaser #iqtest{}",
                        num_q, shorts_tag
                    );

                    match upload_to_youtube_internal(&pool_clone, video_path.clone(), title, description).await {
                        Ok(video_id) => {
                            VIDEOS_UPLOADED.fetch_add(1, Ordering::SeqCst);
                            println!("Uploaded: https://youtube.com/watch?v={}", video_id);

                            // Try to upload thumbnail
                            let thumbnail_path = video_path.replace(".mp4", "_thumb.jpg");
                            if std::path::Path::new(&thumbnail_path).exists() {
                                if let Some(token) = crate::youtube::get_setting_internal(&pool_clone, "youtube_access_token").await {
                                    if let Err(e) = upload_thumbnail(&token, &video_id, &thumbnail_path).await {
                                        println!("Thumbnail upload failed: {}", e);
                                    } else {
                                        println!("Thumbnail uploaded for video {}", video_id);
                                    }
                                }
                                let _ = fs::remove_file(&thumbnail_path);
                            }

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

async fn upload_thumbnail(
    access_token: &str,
    video_id: &str,
    thumbnail_path: &str,
) -> Result<(), String> {
    let thumbnail_data = fs::read(thumbnail_path)
        .map_err(|e| format!("Failed to read thumbnail: {}", e))?;

    let client = reqwest::Client::new();

    let response = client
        .post(format!(
            "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={}",
            video_id
        ))
        .header("Authorization", format!("Bearer {}", access_token))
        .header("Content-Type", "image/jpeg")
        .body(thumbnail_data)
        .send()
        .await
        .map_err(|e| format!("Thumbnail upload failed: {}", e))?;

    if !response.status().is_success() {
        let error_text = response.text().await.unwrap_or_default();
        return Err(format!("Thumbnail upload failed: {}", error_text));
    }

    Ok(())
}

async fn upload_to_youtube_internal(
    pool: &SqlitePool,
    video_path: String,
    title: String,
    description: String,
) -> Result<String, String> {
    // Try upload, refresh token on 401 and retry once
    match try_upload(pool, &video_path, &title, &description).await {
        Ok(id) => Ok(id),
        Err(e) if e.contains("401") || e.contains("UNAUTHENTICATED") || e.contains("Invalid Credentials") => {
            log::info!("Token expired, attempting refresh...");
            // Refresh the token
            crate::youtube::refresh_access_token(pool).await?;
            // Retry upload with new token
            try_upload(pool, &video_path, &title, &description).await
        }
        Err(e) => Err(e),
    }
}

async fn try_upload(
    pool: &SqlitePool,
    video_path: &str,
    title: &str,
    description: &str,
) -> Result<String, String> {
    let access_token = crate::youtube::get_setting_internal(pool, "youtube_access_token")
        .await
        .ok_or("Not authenticated with YouTube")?;

    let video_data = fs::read(video_path)
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
