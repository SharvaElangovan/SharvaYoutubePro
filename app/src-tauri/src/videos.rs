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
            let num_q = config.num_questions.unwrap_or(10);
            let q_time = config.question_time.unwrap_or(5);
            let a_time = config.answer_time.unwrap_or(3);

            format!(r#"
import sys
sys.path.insert(0, '{}')
from generators import GeneralKnowledgeGenerator
from generators.general_knowledge import SAMPLE_QUESTIONS
import random

questions = random.sample(SAMPLE_QUESTIONS, min({}, len(SAMPLE_QUESTIONS)))
generator = GeneralKnowledgeGenerator()
generator.question_time = {}
generator.answer_time = {}
output = generator.generate(questions, '{}')
print(output)
"#, VIDEO_GENERATOR_PATH, num_q, q_time, a_time, output_filename)
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
