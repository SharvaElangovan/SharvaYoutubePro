# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SharvaYoutubePro is an automated YouTube quiz video generation and upload system. It combines a Tauri desktop app (React + Rust) with Python video generators to create and upload quiz videos to YouTube automatically via cron jobs.

## Commands

### Running the Desktop App
```bash
./start.sh          # Start Tauri app in background
./start.sh restart  # Restart the app
./stop.sh           # Stop the app
```

### Daily Upload (Cron Job)
```bash
# Manual run
./video_generator/venv/bin/python daily_upload.py

# Cron is set for 8 AM UTC:
# 0 8 * * * /path/to/video_generator/venv/bin/python /path/to/daily_upload.py
```

### Question Generators
```bash
./question_generator.sh   # Starts parallel_mistral.py and mistral_riddles.py
```

### Video Generator (Standalone)
```bash
cd video_generator
./run.sh            # CLI interface
./run_gui.sh        # GUI application
```

### Tauri App Development
```bash
cd app
npm install
npm run tauri dev   # Development mode
npm run tauri build # Production build
```

## Architecture

### Components

```
SharvaYoutubePro/
├── app/                    # Tauri desktop app
│   ├── src/                # React frontend (TypeScript)
│   └── src-tauri/src/      # Rust backend
│       ├── db.rs           # SQLite database operations
│       ├── questions.rs    # Question bank CRUD
│       ├── videos.rs       # Video generation commands
│       └── youtube.rs      # YouTube OAuth & upload
├── video_generator/        # Python video generation
│   ├── generators/         # Video generator classes
│   │   ├── base.py         # BaseVideoGenerator (NVENC encoding)
│   │   ├── shorts.py       # ShortsGenerator (vertical 9:16)
│   │   └── general_knowledge.py  # GeneralKnowledgeGenerator (16:9)
│   └── sound_effects.py    # TTS via Piper, SFX generation
├── question_generator/     # Mistral/Ollama question generation
├── daily_upload.py         # Main cron job script
└── hourly_upload.py        # Alternative hourly upload strategy
```

### Data Flow

1. **Question Generation**: Ollama + Mistral generates questions → SQLite database
2. **Video Generation**: Python generators create frames → FFmpeg/NVENC encodes MP4
3. **Upload**: daily_upload.py fetches unused questions → generates video → uploads via YouTube API → marks questions used

### Database

Located at: `~/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db`

Key tables:
- `question_bank` - 750k+ questions with `times_used` tracking
- `settings` - YouTube OAuth tokens, SMTP config, Discord webhook

### YouTube API

- Uses OAuth 2.0 with auto token refresh
- Quota resets at midnight Pacific (8 AM UTC)
- ~100 uploads/day with default 10,000 unit quota (1600 units per upload)

## Key Configuration

### Paths (use relative paths from SCRIPT_DIR)
```python
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_GEN_PATH = os.path.join(SCRIPT_DIR, "video_generator")
```

### NVENC Settings (video_generator/generators/base.py)
```python
# RTX 4000 optimized
encoder_args = ['-c:v', 'h264_nvenc', '-preset', 'p1', '-rc', 'vbr', '-cq', '20', '-b:v', '10M']
```

### TTS Workers (video_generator/sound_effects.py)
Limited to 4 parallel workers to prevent system instability.

## Database Backup

Google Drive: https://drive.google.com/drive/folders/1g-wtQde13DutWT5Xc0x06ryQFJWgBR1L

Restore:
```bash
cp ~/Downloads/sharva_youtube_pro.db ~/.local/share/com.sharva.youtube-pro/
```
