# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python application for generating quiz and puzzle videos (MP4) with multiple video types: General Knowledge Quiz, Spot the Difference, Odd One Out, and Emoji Word puzzles. Supports both CLI and GUI interfaces.

## Commands

### Running the Application

```bash
# CLI interface (interactive menu)
./run.sh

# GUI application (tkinter)
./run_gui.sh

# AI-powered quiz generator (requires Ollama)
./run_ai_generator.sh
```

All scripts auto-create a virtual environment if needed and install dependencies.

### Manual Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Direct Execution

```bash
source venv/bin/activate
python3 main.py      # CLI
python3 gui.py       # GUI
python3 ai_json_generator.py  # AI generator (requires Ollama running)
```

## Architecture

### Entry Points
- `main.py` - CLI menu-driven interface
- `gui.py` - Tkinter GUI with tabs for each video type
- `ai_json_generator.py` - Standalone GUI for AI-generated quiz content via local Ollama

### Video Generators (`generators/`)
All generators inherit from `BaseVideoGenerator`:

- `base.py` - Base class with video encoding, text rendering, frame creation. Uses FFmpeg directly (piped raw frames) with NVENC GPU acceleration when available.
- `general_knowledge.py` - Multiple-choice quiz videos with TTS narration
- `spot_difference.py` - Side-by-side image puzzles with difference detection
- `odd_one_out.py` - Grid puzzles (shape or text based)
- `emoji_word.py` - Emoji rebus puzzles using pilmoji for rendering

### Support Modules
- `ai_image_generator.py` - Generates images via Pollinations.ai API (free, no key needed)
- `image_fetcher.py` - Fetches images from the internet
- `difference_maker.py` - Creates visual differences in images programmatically
- `sound_effects.py` - TTS via gTTS, audio track creation

### Key Dependencies
- `moviepy` - Video processing (legacy methods)
- `Pillow` - Image manipulation
- `pilmoji` - Emoji rendering in images
- `gTTS` - Text-to-speech
- `imageio-ffmpeg` - Bundled FFmpeg binary

### Data Flow
1. Content (questions/puzzles) loaded from JSON or sample data
2. Generator creates PIL Image frames with durations
3. `save_video_fast()` pipes raw frames to FFmpeg for encoding
4. Optional TTS audio mixed in via FFmpeg adelay filters

### Output
- Videos saved to `output/` directory (1920x1080, 24fps MP4)
- AI-generated JSON files saved to `ai_generated/`

## JSON Formats

### General Knowledge Questions
```json
[
  {
    "question": "What is the capital of France?",
    "options": ["London", "Berlin", "Paris", "Madrid"],
    "answer": 2
  }
]
```
Note: `answer` is the 0-based index of the correct option.

### Emoji Puzzles
```json
[
  {
    "emojis": "🌧️ + 🎀",
    "answer": "Rainbow",
    "hint": "Colorful arc in the sky",
    "category": "Nature"
  }
]
```
