"""Sound effects and TTS for quiz videos - using Piper TTS for fast, natural speech."""

import os
import subprocess
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed

# Piper TTS - fast local neural TTS
_piper_voice = None
_piper_available = None
_system_info = None


def _get_system_info():
    """Get system info for parallelization."""
    global _system_info
    if _system_info is not None:
        return _system_info

    import multiprocessing

    info = {
        'cpu_cores': multiprocessing.cpu_count(),
        'gpu_capable': False,
    }

    # Check for capable NVIDIA GPU (for future ONNX GPU support)
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                parts = line.split(', ')
                if len(parts) >= 2:
                    name = parts[0].strip()
                    vram = int(parts[1].strip())
                    # Skip old Quadro K/M series
                    is_old = 'Quadro K' in name or 'Quadro M' in name
                    if vram >= 4000 and not is_old:
                        info['gpu_capable'] = True
                        info['gpu_name'] = name
                        break
    except:
        pass

    _system_info = info
    return info


def _get_piper_voice():
    """Lazy-load Piper voice model."""
    global _piper_voice, _piper_available

    if _piper_available is False:
        return None

    if _piper_voice is not None:
        return _piper_voice

    try:
        from piper import PiperVoice

        # Download and cache voice model
        # Using en_US-lessac-high - one of the most natural sounding voices
        model_dir = os.path.join(os.path.dirname(__file__), 'piper_models')
        os.makedirs(model_dir, exist_ok=True)

        model_name = "en_US-ryan-medium"
        model_path = os.path.join(model_dir, f"{model_name}.onnx")
        config_path = os.path.join(model_dir, f"{model_name}.onnx.json")

        # Download if not exists
        if not os.path.exists(model_path):
            print(f"  Downloading Piper voice model: {model_name}...")
            import urllib.request

            base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium"

            urllib.request.urlretrieve(f"{base_url}/en_US-ryan-medium.onnx", model_path)
            urllib.request.urlretrieve(f"{base_url}/en_US-ryan-medium.onnx.json", config_path)
            print("  Voice model downloaded!")

        _piper_voice = PiperVoice.load(model_path, config_path)
        _piper_available = True
        return _piper_voice

    except ImportError:
        print("  Piper TTS not installed. Install with: pip install piper-tts")
        _piper_available = False
        return None
    except Exception as e:
        print(f"  Piper TTS error: {e}")
        _piper_available = False
        return None


class TTSCache:
    """Pre-generated TTS audio cache for faster video generation."""

    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), 'tts_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self._index_file = os.path.join(self.cache_dir, 'index.json')
        self._index = self._load_index()

    def _load_index(self):
        """Load cache index from disk."""
        try:
            if os.path.exists(self._index_file):
                with open(self._index_file, 'r') as f:
                    import json
                    return json.load(f)
        except:
            pass
        return {}

    def _save_index(self):
        """Save cache index to disk."""
        import json
        with open(self._index_file, 'w') as f:
            json.dump(self._index, f)

    def _text_hash(self, text):
        """Generate hash for text."""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()[:16]

    def get_cached(self, text):
        """Get cached TTS file path if exists."""
        text_hash = self._text_hash(text)
        if text_hash in self._index:
            cache_path = os.path.join(self.cache_dir, self._index[text_hash])
            if os.path.exists(cache_path):
                return cache_path
            else:
                # Cache file missing, remove from index
                del self._index[text_hash]
        return None

    def add_to_cache(self, text, audio_path):
        """Add generated TTS to cache."""
        import shutil
        text_hash = self._text_hash(text)
        cache_filename = f"{text_hash}.mp3"
        cache_path = os.path.join(self.cache_dir, cache_filename)

        # Copy to cache
        shutil.copy2(audio_path, cache_path)
        self._index[text_hash] = cache_filename
        self._save_index()
        return cache_path

    def get_cache_stats(self):
        """Get cache statistics."""
        total_files = len(self._index)
        total_size = sum(
            os.path.getsize(os.path.join(self.cache_dir, f))
            for f in self._index.values()
            if os.path.exists(os.path.join(self.cache_dir, f))
        )
        return {
            'files': total_files,
            'size_mb': round(total_size / (1024 * 1024), 2)
        }

    def prewarm_cache(self, texts, max_workers=None):
        """Pre-generate TTS for a list of texts."""
        sfx = SoundEffects()
        to_generate = []

        for text in texts:
            if not self.get_cached(text):
                to_generate.append(text)

        if not to_generate:
            print(f"  All {len(texts)} texts already cached")
            return

        print(f"  Pre-generating TTS for {len(to_generate)} texts...")

        # Generate in batches
        items = []
        for i, text in enumerate(to_generate):
            temp_path = os.path.join('/tmp', f'_prewarm_{i}.mp3')
            items.append((text, temp_path))

        # Use batch generation
        sfx.text_to_speech_batch(items)

        # Add to cache
        for text, temp_path in items:
            if os.path.exists(temp_path):
                self.add_to_cache(text, temp_path)
                os.remove(temp_path)

        print(f"  Cached {len(to_generate)} new TTS files")


class SoundEffects:
    """Handle sound effects and text-to-speech for videos."""

    def __init__(self, use_cache=True):
        self.sounds_dir = os.path.join(os.path.dirname(__file__), 'sounds')
        os.makedirs(self.sounds_dir, exist_ok=True)
        self.click_sound = os.path.join(self.sounds_dir, 'click.mp3')
        self._ffmpeg_path = None
        self._cache = TTSCache() if use_cache else None

    def _get_ffmpeg(self):
        """Get ffmpeg path."""
        if self._ffmpeg_path is None:
            try:
                import imageio_ffmpeg
                self._ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except:
                self._ffmpeg_path = 'ffmpeg'
        return self._ffmpeg_path

    def text_to_speech(self, text, output_path):
        """Convert text to speech using Piper TTS (fast, local, natural)."""
        # Check cache first
        if self._cache:
            cached = self._cache.get_cached(text)
            if cached:
                import shutil
                shutil.copy2(cached, output_path)
                return output_path

        voice = _get_piper_voice()

        if voice is not None:
            result = self._piper_tts(voice, text, output_path)
        else:
            # Fallback to gTTS if Piper unavailable
            result = self._gtts_fallback(text, output_path)

        # Add to cache if generated successfully
        if result and self._cache and os.path.exists(output_path):
            self._cache.add_to_cache(text, output_path)

        return result

    def _piper_tts(self, voice, text, output_path):
        """Generate TTS using Piper - very fast local synthesis."""
        try:
            # Piper outputs WAV, we'll save as WAV then convert to MP3
            wav_path = output_path.replace('.mp3', '.wav')

            # Collect audio from synthesize generator (piper-tts 1.3+ API)
            audio_bytes = b''
            sample_rate = voice.config.sample_rate
            for chunk in voice.synthesize(text):
                audio_bytes += chunk.audio_int16_bytes

            # Write WAV file manually
            with wave.open(wav_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes)

            # Convert to MP3 using ffmpeg for smaller file size
            ffmpeg = self._get_ffmpeg()

            cmd = [
                ffmpeg, '-y',
                '-i', wav_path,
                '-c:a', 'libmp3lame', '-q:a', '2',
                output_path
            ]
            subprocess.run(cmd, capture_output=True, timeout=30)

            # Clean up WAV
            try:
                os.remove(wav_path)
            except:
                pass

            return output_path

        except Exception as e:
            print(f"  Piper TTS error: {e}")
            return self._gtts_fallback(text, output_path)

    def _gtts_fallback(self, text, output_path):
        """Fallback to gTTS if Piper is not available."""
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(output_path)
            return output_path
        except Exception as e:
            print(f"  TTS error: {e}")
            return None

    def text_to_speech_batch(self, items):
        """
        Generate multiple TTS files in parallel using all CPU cores.

        Args:
            items: List of (text, output_path) tuples

        Returns:
            List of successfully generated output paths
        """
        if not items:
            return []

        sys_info = _get_system_info()
        # Limit to 4 workers to prevent system instability
        max_workers = min(4, sys_info['cpu_cores'])

        print(f"  Generating {len(items)} TTS files in parallel ({max_workers} workers)...")

        # Pre-load Piper voice (once, before threading)
        _get_piper_voice()

        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all TTS jobs
            future_to_path = {
                executor.submit(self.text_to_speech, text, path): path
                for text, path in items
            }

            # Collect results as they complete
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"  TTS failed for {path}: {e}")

        print(f"  Generated {len(results)}/{len(items)} TTS files")
        return results

    def get_click_sound(self):
        """Get path to click sound."""
        return self.click_sound if os.path.exists(self.click_sound) else None


class AudioEnhancements:
    """Enhanced audio features - background music, sound effects, ducking."""

    def __init__(self):
        self.assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
        self.music_dir = os.path.join(self.assets_dir, 'music')
        self.sfx_dir = os.path.join(self.assets_dir, 'sfx')
        os.makedirs(self.music_dir, exist_ok=True)
        os.makedirs(self.sfx_dir, exist_ok=True)
        self._ffmpeg_path = None

    def _get_ffmpeg(self):
        if self._ffmpeg_path is None:
            try:
                import imageio_ffmpeg
                self._ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except:
                self._ffmpeg_path = 'ffmpeg'
        return self._ffmpeg_path

    def generate_sfx(self, force_regenerate=False):
        """Generate sound effects if they don't exist."""
        ffmpeg = self._get_ffmpeg()
        sfx_paths = {}

        # Correct sound (pleasant double ding - C5 and E5 notes)
        correct_path = os.path.join(self.sfx_dir, 'correct.mp3')
        sfx_paths['correct'] = correct_path
        if not os.path.exists(correct_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=523:duration=0.15',  # C5
                '-f', 'lavfi', '-i', 'sine=frequency=659:duration=0.2',   # E5
                '-filter_complex', '[0]adelay=0|0[a];[1]adelay=100|100[b];[a][b]amix=inputs=2:normalize=0,afade=t=out:st=0.2:d=0.1',
                '-c:a', 'libmp3lame', '-q:a', '2',
                correct_path
            ]
            subprocess.run(cmd, capture_output=True)

        # Wrong sound (harsh buzzer)
        wrong_path = os.path.join(self.sfx_dir, 'wrong.mp3')
        sfx_paths['wrong'] = wrong_path
        if not os.path.exists(wrong_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=150:duration=0.4',
                '-af', 'tremolo=f=20:d=0.8,afade=t=out:st=0.2:d=0.2',
                '-c:a', 'libmp3lame', '-q:a', '2',
                wrong_path
            ]
            subprocess.run(cmd, capture_output=True)

        # Tick sound (for timer countdown)
        tick_path = os.path.join(self.sfx_dir, 'tick.mp3')
        sfx_paths['tick'] = tick_path
        if not os.path.exists(tick_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=800:duration=0.08',
                '-af', 'afade=t=out:st=0.05:d=0.03',
                '-c:a', 'libmp3lame', '-q:a', '2',
                tick_path
            ]
            subprocess.run(cmd, capture_output=True)

        # Timer warning (urgent beep for last 3 seconds)
        warning_path = os.path.join(self.sfx_dir, 'warning.mp3')
        sfx_paths['warning'] = warning_path
        if not os.path.exists(warning_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=1200:duration=0.1',
                '-af', 'afade=t=in:st=0:d=0.02,afade=t=out:st=0.08:d=0.02',
                '-c:a', 'libmp3lame', '-q:a', '2',
                warning_path
            ]
            subprocess.run(cmd, capture_output=True)

        # Whoosh sound (for transitions)
        whoosh_path = os.path.join(self.sfx_dir, 'whoosh.mp3')
        sfx_paths['whoosh'] = whoosh_path
        if not os.path.exists(whoosh_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'anoisesrc=d=0.3:c=pink:a=0.3',
                '-af', 'lowpass=f=2000,highpass=f=200,afade=t=in:st=0:d=0.1,afade=t=out:st=0.15:d=0.15',
                '-c:a', 'libmp3lame', '-q:a', '2',
                whoosh_path
            ]
            subprocess.run(cmd, capture_output=True)

        # Pop sound (for option selection)
        pop_path = os.path.join(self.sfx_dir, 'pop.mp3')
        sfx_paths['pop'] = pop_path
        if not os.path.exists(pop_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=400:duration=0.1',
                '-af', 'asetrate=44100*1.5,atempo=0.67,afade=t=out:st=0.05:d=0.05',
                '-c:a', 'libmp3lame', '-q:a', '2',
                pop_path
            ]
            subprocess.run(cmd, capture_output=True)

        # Ding sound (notification style)
        ding_path = os.path.join(self.sfx_dir, 'ding.mp3')
        sfx_paths['ding'] = ding_path
        if not os.path.exists(ding_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=1047:duration=0.5',  # C6
                '-af', 'afade=t=out:st=0.1:d=0.4',
                '-c:a', 'libmp3lame', '-q:a', '2',
                ding_path
            ]
            subprocess.run(cmd, capture_output=True)

        # Countdown beep (3-2-1 style)
        countdown_path = os.path.join(self.sfx_dir, 'countdown.mp3')
        sfx_paths['countdown'] = countdown_path
        if not os.path.exists(countdown_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=600:duration=0.15',
                '-af', 'afade=t=out:st=0.1:d=0.05',
                '-c:a', 'libmp3lame', '-q:a', '2',
                countdown_path
            ]
            subprocess.run(cmd, capture_output=True)

        # Final countdown (higher pitch for "GO!")
        go_path = os.path.join(self.sfx_dir, 'go.mp3')
        sfx_paths['go'] = go_path
        if not os.path.exists(go_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=880:duration=0.3',
                '-af', 'afade=t=out:st=0.15:d=0.15',
                '-c:a', 'libmp3lame', '-q:a', '2',
                go_path
            ]
            subprocess.run(cmd, capture_output=True)

        # Streak sound (ascending notes for combo)
        streak_path = os.path.join(self.sfx_dir, 'streak.mp3')
        sfx_paths['streak'] = streak_path
        if not os.path.exists(streak_path) or force_regenerate:
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1',   # A4
                '-f', 'lavfi', '-i', 'sine=frequency=554:duration=0.1',   # C#5
                '-f', 'lavfi', '-i', 'sine=frequency=659:duration=0.15',  # E5
                '-filter_complex', '[0]adelay=0|0[a];[1]adelay=80|80[b];[2]adelay=160|160[c];[a][b][c]amix=inputs=3:normalize=0,afade=t=out:st=0.2:d=0.1',
                '-c:a', 'libmp3lame', '-q:a', '2',
                streak_path
            ]
            subprocess.run(cmd, capture_output=True)

        return sfx_paths

    def generate_background_music(self, duration, output_path):
        """Generate simple looping background beat."""
        ffmpeg = self._get_ffmpeg()

        # Check for existing music files first
        existing_music = [f for f in os.listdir(self.music_dir) if f.endswith(('.mp3', '.wav', '.m4a'))]
        if existing_music:
            music_file = os.path.join(self.music_dir, existing_music[0])
            # Loop the existing music to match duration
            cmd = [
                ffmpeg, '-y',
                '-stream_loop', '-1',
                '-i', music_file,
                '-t', str(duration),
                '-af', 'volume=0.15',  # Low volume for background
                '-c:a', 'libmp3lame', '-q:a', '4',
                output_path
            ]
            subprocess.run(cmd, capture_output=True)
            return output_path

        # Generate a simple ambient tone if no music exists
        cmd = [
            ffmpeg, '-y',
            '-f', 'lavfi',
            '-i', f'sine=frequency=220:duration={duration}',
            '-af', 'volume=0.05,lowpass=f=400',
            '-c:a', 'libmp3lame', '-q:a', '4',
            output_path
        ]
        subprocess.run(cmd, capture_output=True)
        return output_path

    def mix_audio_with_music(self, video_path, tts_events, sfx_events=None, music_volume=0.15, output_path=None):
        """
        Mix TTS, sound effects, and background music into video.

        Args:
            video_path: Input video file
            tts_events: List of (timestamp, audio_file) for TTS
            sfx_events: List of (timestamp, sfx_type) for sound effects ('correct', 'wrong')
            music_volume: Background music volume (0.0 - 1.0)
            output_path: Output video path (default: replace input)
        """
        ffmpeg = self._get_ffmpeg()
        if output_path is None:
            output_path = video_path.replace('.mp4', '_enhanced.mp4')

        # Get video duration
        probe_cmd = [
            ffmpeg, '-i', video_path,
            '-f', 'null', '-'
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        # Parse duration from stderr (FFmpeg outputs info there)
        import re
        duration_match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})', result.stderr)
        if duration_match:
            h, m, s = map(int, duration_match.groups())
            duration = h * 3600 + m * 60 + s + 5  # Add buffer
        else:
            duration = 60  # Default

        # Generate background music
        music_path = os.path.join(self.sfx_dir, '_temp_music.mp3')
        self.generate_background_music(duration, music_path)

        # Generate SFX files
        sfx_files = self.generate_sfx()

        # Build FFmpeg filter
        inputs = ['-i', video_path, '-i', music_path]
        filter_parts = []
        input_idx = 2

        # Background music with ducking
        filter_parts.append(f'[1]volume={music_volume}[music]')

        # Add TTS events
        valid_tts = [(i, t, f) for i, (t, f) in enumerate(tts_events) if os.path.exists(f)]
        tts_labels = []
        for idx, (i, timestamp, audio_file) in enumerate(valid_tts):
            inputs.extend(['-i', audio_file])
            delay_ms = int(timestamp * 1000)
            label = f'tts{idx}'
            filter_parts.append(f'[{input_idx}]adelay={delay_ms}|{delay_ms},aformat=sample_rates=44100:channel_layouts=stereo[{label}]')
            tts_labels.append(f'[{label}]')
            input_idx += 1

        # Add SFX events
        sfx_labels = []
        if sfx_events:
            for idx, (timestamp, sfx_type) in enumerate(sfx_events):
                sfx_file = sfx_files.get(sfx_type)
                if sfx_file and os.path.exists(sfx_file):
                    inputs.extend(['-i', sfx_file])
                    delay_ms = int(timestamp * 1000)
                    label = f'sfx{idx}'
                    filter_parts.append(f'[{input_idx}]adelay={delay_ms}|{delay_ms},volume=0.8[{label}]')
                    sfx_labels.append(f'[{label}]')
                    input_idx += 1

        # Mix all audio together
        all_audio = '[music]' + ''.join(tts_labels) + ''.join(sfx_labels)
        num_inputs = 1 + len(valid_tts) + len(sfx_labels)
        filter_parts.append(f'{all_audio}amix=inputs={num_inputs}:normalize=0[aout]')

        filter_complex = ';'.join(filter_parts)

        cmd = [
            ffmpeg, '-y',
            *inputs,
            '-filter_complex', filter_complex,
            '-map', '0:v',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        # Cleanup temp music
        try:
            os.remove(music_path)
        except:
            pass

        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
        else:
            print(f"Audio mix error: {result.stderr[:500]}")
            return video_path


def create_quiz_audio(duration, events, output_path):
    """
    Create audio track - simplified version that just concatenates TTS files.
    """
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    # Filter to only TTS files (skip click sounds to speed up)
    tts_events = [(t, f) for t, f in events if f and os.path.exists(f) and 'tts' in f]

    if not tts_events:
        # No TTS, create silent audio
        cmd = [
            ffmpeg, '-y',
            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
            '-t', str(duration),
            '-c:a', 'aac', '-b:a', '128k',
            output_path
        ]
        subprocess.run(cmd, capture_output=True)
        return output_path

    # Simple approach: create audio with just the TTS at their timestamps
    # Using concat with silence padding

    temp_files = []
    current_pos = 0

    for i, (event_time, audio_file) in enumerate(tts_events):
        # Add silence before this event
        silence_duration = event_time - current_pos
        if silence_duration > 0:
            silence_file = f'/tmp/_silence_{i}.m4a'
            cmd = [
                ffmpeg, '-y',
                '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                '-t', str(silence_duration),
                '-c:a', 'aac', '-b:a', '128k',
                silence_file
            ]
            subprocess.run(cmd, capture_output=True)
            temp_files.append(silence_file)

        # Convert TTS to m4a
        converted = f'/tmp/_tts_converted_{i}.m4a'
        cmd = [
            ffmpeg, '-y',
            '-i', audio_file,
            '-c:a', 'aac', '-b:a', '128k',
            converted
        ]
        subprocess.run(cmd, capture_output=True)
        temp_files.append(converted)

        # Get duration of this audio
        probe_cmd = [ffmpeg, '-i', audio_file, '-f', 'null', '-']
        subprocess.run(probe_cmd, capture_output=True, text=True)
        # Estimate 2 seconds per TTS
        current_pos = event_time + 2

    # Add final silence if needed
    if current_pos < duration:
        silence_file = '/tmp/_silence_final.m4a'
        cmd = [
            ffmpeg, '-y',
            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
            '-t', str(duration - current_pos),
            '-c:a', 'aac', '-b:a', '128k',
            silence_file
        ]
        subprocess.run(cmd, capture_output=True)
        temp_files.append(silence_file)

    # Create concat file
    concat_file = '/tmp/_concat_list.txt'
    with open(concat_file, 'w') as f:
        for tf in temp_files:
            f.write(f"file '{tf}'\n")

    # Concat all
    cmd = [
        ffmpeg, '-y',
        '-f', 'concat', '-safe', '0',
        '-i', concat_file,
        '-c:a', 'aac', '-b:a', '128k',
        output_path
    ]
    subprocess.run(cmd, capture_output=True)

    # Cleanup
    for tf in temp_files:
        try:
            os.remove(tf)
        except:
            pass
    try:
        os.remove(concat_file)
    except:
        pass

    return output_path


import random
import sqlite3

# Topic categories for themed videos
TOPIC_CATEGORIES = {
    'Science': {
        'topic_ids': [3, 10, 8, 9],  # Science, Biology, Physics, Chemistry
        'emoji': '🔬',
        'keywords': ['Science', 'STEM', 'Scientific']
    },
    'History': {
        'topic_ids': [4],
        'emoji': '📜',
        'keywords': ['History', 'Historical', 'Past']
    },
    'Geography': {
        'topic_ids': [5],
        'emoji': '🌍',
        'keywords': ['Geography', 'World', 'Countries']
    },
    'Entertainment': {
        'topic_ids': [101, 102, 103, 104],  # Movies, TV, Music, Video Games
        'emoji': '🎬',
        'keywords': ['Entertainment', 'Pop Culture', 'Movies & Music']
    },
    'Sports': {
        'topic_ids': [301, 302, 303, 304, 305, 306],  # Football, Basketball, etc.
        'emoji': '⚽',
        'keywords': ['Sports', 'Athletics', 'Games']
    },
    'Nature': {
        'topic_ids': [400, 401, 402, 403],  # Nature, Animals, Plants, Oceans
        'emoji': '🦁',
        'keywords': ['Nature', 'Animals', 'Wildlife']
    },
    'Technology': {
        'topic_ids': [201, 205],  # Computers, AI
        'emoji': '💻',
        'keywords': ['Technology', 'Tech', 'Computers']
    },
    'Literature': {
        'topic_ids': [6],
        'emoji': '📚',
        'keywords': ['Literature', 'Books', 'Authors']
    },
    'Food': {
        'topic_ids': [600],
        'emoji': '🍕',
        'keywords': ['Food', 'Cooking', 'Cuisine']
    },
    'Space': {
        'topic_ids': [901],  # Solar System
        'emoji': '🚀',
        'keywords': ['Space', 'Astronomy', 'Universe']
    },
    'General Knowledge': {
        'topic_ids': [1, 2],  # Academic, Mathematics
        'emoji': '🧠',
        'keywords': ['General Knowledge', 'Trivia', 'Mixed']
    },
    'Culture': {
        'topic_ids': [700, 703, 15],  # World Culture, Religions, Art & Music
        'emoji': '🎨',
        'keywords': ['Culture', 'Art', 'World']
    },
}


class TopicCategories:
    """Manage themed quiz categories and question fetching."""

    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.expanduser(
            '~/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db'
        )

    @staticmethod
    def get_all_categories():
        """Get list of all available category names."""
        return list(TOPIC_CATEGORIES.keys())

    @staticmethod
    def get_category_info(category_name):
        """Get info for a specific category."""
        return TOPIC_CATEGORIES.get(category_name)

    def get_questions_by_category(self, category_name, count, for_shorts=False, difficulty=None):
        """
        Fetch unused questions from a specific category.

        Args:
            category_name: Name from TOPIC_CATEGORIES
            count: Number of questions to fetch
            for_shorts: If True, use shorter question length filter
            difficulty: 'easy' (1-2), 'medium' (3), 'hard' (4-5), or None for all

        Returns:
            Tuple of (questions_list, question_ids)
        """
        category = TOPIC_CATEGORIES.get(category_name)
        if not category:
            return [], []

        topic_ids = category['topic_ids']
        length_filter = "BETWEEN 20 AND 120" if for_shorts else "BETWEEN 20 AND 200"
        placeholders = ','.join('?' * len(topic_ids))

        # Difficulty filter
        if difficulty == 'easy':
            diff_filter = "AND difficulty IN (1, 2)"
        elif difficulty == 'medium':
            diff_filter = "AND difficulty = 3"
        elif difficulty == 'hard':
            diff_filter = "AND difficulty IN (4, 5)"
        else:
            diff_filter = ""

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(f'''
            SELECT id, question, option_a, option_b, option_c, option_d, correct_answer
            FROM question_bank
            WHERE times_used = 0
            AND topic_id IN ({placeholders})
            AND length(question) {length_filter}
            AND length(option_a) BETWEEN 1 AND 50
            AND length(option_b) BETWEEN 1 AND 50
            AND length(option_c) BETWEEN 1 AND 50
            AND length(option_d) BETWEEN 1 AND 50
            AND question NOT LIKE '%[%]%'
            AND question NOT LIKE '%http%'
            AND question LIKE '%?%'
            {diff_filter}
            ORDER BY RANDOM()
            LIMIT ?
        ''', (*topic_ids, count))

        rows = cur.fetchall()
        conn.close()

        questions = []
        ids = []
        for row in rows:
            ids.append(row[0])
            questions.append({
                'question': row[1],
                'options': [row[2], row[3], row[4], row[5]],
                'answer': row[6]
            })
        return questions, ids

    def get_questions_by_difficulty(self, count, difficulty='medium', for_shorts=False):
        """Fetch questions by difficulty across all topics."""
        length_filter = "BETWEEN 20 AND 120" if for_shorts else "BETWEEN 20 AND 200"

        if difficulty == 'easy':
            diff_filter = "difficulty IN (1, 2)"
        elif difficulty == 'hard':
            diff_filter = "difficulty IN (4, 5)"
        else:
            diff_filter = "difficulty = 3"

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(f'''
            SELECT id, question, option_a, option_b, option_c, option_d, correct_answer
            FROM question_bank
            WHERE times_used = 0
            AND {diff_filter}
            AND length(question) {length_filter}
            AND length(option_a) BETWEEN 1 AND 50
            AND length(option_b) BETWEEN 1 AND 50
            AND length(option_c) BETWEEN 1 AND 50
            AND length(option_d) BETWEEN 1 AND 50
            AND question NOT LIKE '%[%]%'
            AND question NOT LIKE '%http%'
            AND question LIKE '%?%'
            ORDER BY RANDOM()
            LIMIT ?
        ''', (count,))

        rows = cur.fetchall()
        conn.close()

        questions = []
        ids = []
        for row in rows:
            ids.append(row[0])
            questions.append({
                'question': row[1],
                'options': [row[2], row[3], row[4], row[5]],
                'answer': row[6]
            })
        return questions, ids

    def get_category_question_count(self, category_name, unused_only=True):
        """Get count of available questions in a category."""
        category = TOPIC_CATEGORIES.get(category_name)
        if not category:
            return 0

        topic_ids = category['topic_ids']
        placeholders = ','.join('?' * len(topic_ids))

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        where_clause = "times_used = 0 AND" if unused_only else ""
        cur.execute(f'''
            SELECT COUNT(*) FROM question_bank
            WHERE {where_clause} topic_id IN ({placeholders})
        ''', topic_ids)

        count = cur.fetchone()[0]
        conn.close()
        return count

    def get_best_category_for_video(self, min_questions=50):
        """Find the category with most unused questions."""
        best = None
        best_count = 0

        for category_name in TOPIC_CATEGORIES:
            count = self.get_category_question_count(category_name)
            if count >= min_questions and count > best_count:
                best = category_name
                best_count = count

        return best, best_count


class TitleGenerator:
    """Generate engaging clickbait titles for quiz videos."""

    TEMPLATES_SHORTS = [
        "Only {percent}% Can Score {score}/{total}! 🧠",
        "Can You Beat This Quiz? 😱",
        "IMPOSSIBLE Quiz - {score}/{total} Challenge",
        "I Bet You Can't Answer #{num} 🤔",
        "This Quiz Broke The Internet! 🔥",
        "Your IQ If You Pass: GENIUS 🧠✨",
        "Nobody Gets #{num} Right! 😤",
        "Quiz Time! Comment Your Score 👇",
        "How Smart Are You? Take This Quiz!",
        "Only Big Brains Can Score {score}/{total} 🎯",
        "WARNING: This Quiz Is HARD! ⚠️",
        "The Question Everyone Gets Wrong 🤯",
        "Can Your Brain Handle This? 🧠🔥",
        "Trivia Master or Trivia Disaster? 🎲",
        "{score} Questions - {time} Seconds ⏰",
    ]

    TEMPLATES_LONGFORM = [
        "{num} Trivia Questions - General Knowledge Quiz",
        "Ultimate {topic} Quiz - {num} Questions",
        "Can You Score {score}/{num}? Take The Challenge!",
        "The Hardest {topic} Quiz On YouTube",
        "{num} Questions That Will Test Your Knowledge",
        "How Many Can You Get Right? {num} Question Quiz",
        "Brain Test: {num} Trivia Questions",
        "Quiz Night: {num} Questions Across All Topics",
        "The Ultimate Knowledge Test - {num} Questions",
        "Are You Smarter Than Average? {num} Questions",
    ]

    # Themed templates for specific categories
    THEMED_TEMPLATES_SHORTS = {
        'Science': [
            "Science Quiz - Only {percent}% Pass! 🔬",
            "{emoji} Can You Answer These Science Questions?",
            "STEM Challenge: {score}/{total} Quiz 🧪",
        ],
        'History': [
            "History Buffs ONLY! {emoji} Quiz Challenge",
            "Do You Know Your History? {score}/{total} Test 📜",
            "Ancient to Modern: History Quiz! ⏳",
        ],
        'Sports': [
            "Sports Fan? Prove It! {emoji} Quiz",
            "Only TRUE Fans Score {score}/{total}! ⚽",
            "Sports Trivia Challenge! {emoji}",
        ],
        'Entertainment': [
            "Movie Buff Challenge! {emoji} {score}/{total}",
            "Pop Culture Quiz - Do You Know It? 🎬",
            "Entertainment Trivia! Only {percent}% Pass 🎵",
        ],
        'Nature': [
            "Animal Kingdom Quiz! {emoji} Can You Pass?",
            "Nature Lovers: {score}/{total} Challenge 🌿",
            "Wildlife Trivia! Only {percent}% Know This 🦁",
        ],
        'Geography': [
            "Geography Genius? {emoji} Test Yourself!",
            "World Geography Quiz - {score}/{total} 🌍",
            "Can You Name These Countries? 🗺️",
        ],
        'Food': [
            "Foodie Quiz! {emoji} How Much Do You Know?",
            "Cooking Trivia - Only Chefs Pass! 👨‍🍳",
            "Food & Cuisine: {score}/{total} Challenge 🍕",
        ],
        'Space': [
            "Space Quiz! {emoji} Are You An Expert?",
            "Astronomy Trivia - Only {percent}% Pass! 🌟",
            "Cosmic Challenge: {score}/{total} 🚀",
        ],
    }

    THEMED_TEMPLATES_LONGFORM = {
        'Science': [
            "{num} Science Questions - Ultimate STEM Quiz {emoji}",
            "The Hardest Science Quiz: {num} Questions 🔬",
            "Science Trivia Marathon - {num} Questions! 🧪",
        ],
        'History': [
            "{num} History Questions - Test Your Knowledge {emoji}",
            "History Through The Ages: {num} Question Quiz 📜",
            "World History Challenge - {num} Questions! ⏳",
        ],
        'Sports': [
            "{num} Sports Questions - Ultimate Fan Quiz {emoji}",
            "Sports Trivia: {num} Questions Across All Sports ⚽",
            "Are You A True Sports Fan? {num} Questions! 🏆",
        ],
        'Entertainment': [
            "Movies, Music & More: {num} Entertainment Questions {emoji}",
            "Pop Culture Quiz - {num} Questions! 🎬",
            "The Ultimate Entertainment Challenge: {num} Questions 🎵",
        ],
        'Nature': [
            "Animal & Nature Quiz - {num} Questions {emoji}",
            "Wildlife Trivia: {num} Questions About Nature 🌿",
            "The Natural World: {num} Question Challenge! 🦁",
        ],
    }

    EMOJIS = ["🧠", "🤔", "😱", "🔥", "✨", "🎯", "⚠️", "🤯", "💡", "📚", "🎲", "⏰"]

    DIFFICULTY_TEMPLATES = {
        'easy': [
            "EASY Quiz - Can You Score {score}/{total}? 🟢",
            "Beginner Trivia - Everyone Should Know This! ✅",
            "Easy Mode Quiz - Perfect Score Challenge! 🌟",
        ],
        'medium': [
            "Medium Quiz - Test Your Knowledge! 🟡",
            "Can You Handle This Quiz? 🤔",
            "Average Brain vs This Quiz! 🧠",
        ],
        'hard': [
            "IMPOSSIBLE Quiz - Only Geniuses Pass! 🔴",
            "HARD MODE - 99% Will Fail! 😱",
            "Expert Only Quiz - Are You Smart Enough? 💀",
            "This Quiz Will Break Your Brain! 🤯",
        ],
    }

    @classmethod
    def generate_shorts_title(cls, num_questions=5, category=None, difficulty=None):
        """Generate an engaging title for a Shorts video."""
        # Use difficulty template if provided
        if difficulty and difficulty in cls.DIFFICULTY_TEMPLATES:
            template = random.choice(cls.DIFFICULTY_TEMPLATES[difficulty])
            emoji = '🧠'
        # Use themed template if category provided
        elif category and category in cls.THEMED_TEMPLATES_SHORTS:
            template = random.choice(cls.THEMED_TEMPLATES_SHORTS[category])
            cat_info = TOPIC_CATEGORIES.get(category, {})
            emoji = cat_info.get('emoji', '🧠')
        else:
            template = random.choice(cls.TEMPLATES_SHORTS)
            emoji = random.choice(cls.EMOJIS)

        return template.format(
            percent=random.choice([1, 2, 3, 5, 10]),
            score=num_questions,
            total=num_questions,
            num=random.randint(1, num_questions),
            time=num_questions * 10,
            emoji=emoji
        )

    @classmethod
    def generate_longform_title(cls, num_questions=50, topic="General Knowledge", category=None):
        """Generate an engaging title for a long-form video."""
        # Use themed template if category provided
        if category and category in cls.THEMED_TEMPLATES_LONGFORM:
            template = random.choice(cls.THEMED_TEMPLATES_LONGFORM[category])
            cat_info = TOPIC_CATEGORIES.get(category, {})
            emoji = cat_info.get('emoji', '🧠')
            topic = category  # Use category name as topic
        else:
            template = random.choice(cls.TEMPLATES_LONGFORM)
            emoji = random.choice(cls.EMOJIS)

        return template.format(
            num=num_questions,
            topic=topic,
            score=int(num_questions * 0.8),
            emoji=emoji
        )

    @classmethod
    def generate_description(cls, num_questions, is_shorts=False, category=None):
        """Generate video description."""
        cat_info = TOPIC_CATEGORIES.get(category, {}) if category else {}
        emoji = cat_info.get('emoji', '🧠')
        keywords = cat_info.get('keywords', ['trivia', 'generalknowledge'])
        hashtags = ' '.join([f'#{k.lower().replace(" ", "")}' for k in keywords[:3]])

        if is_shorts:
            topic_text = f"{category} " if category else ""
            return f"""{emoji} Test your brain with {num_questions} quick {topic_text}trivia questions!

Comment your score below! 👇
Can you beat it? Challenge your friends!

#quiz #trivia #shorts #brainteaser {hashtags}

Subscribe for daily quizzes! 🔔"""
        else:
            topic_text = f"about {category}" if category else "covering various topics"
            return f"""Welcome to another trivia challenge! {emoji}

This video contains {num_questions} questions {topic_text}.
Pause the video to think, then see if you got it right!

⏱️ Question Time: 10 seconds
✅ Answer Reveal: 5 seconds

📊 Comment your final score below!
🔔 Subscribe for more quiz content!

#quiz #trivia {hashtags} #brainteaser #challenge"""
