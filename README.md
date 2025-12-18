# Transcribe

CLI tool for transcribing meetings with speaker diarization. Captures both your microphone and system audio (what you hear), then transcribes using the OpenAI API.

**Works on Windows and macOS.**

## Features

- Dual audio capture (mic + system audio)
- Automatic speaker labeling ("Moi" vs "Interlocuteur")
- Transcription via OpenAI API (gpt-4o-transcribe, gpt-4o-mini-transcribe, whisper-1)
- Multiple output formats (TXT, JSON, SRT)
- Debug tools for troubleshooting

## Prerequisites

- Python 3.9+
- FFmpeg
- OpenAI API key
- macOS 12+ or Windows 10+

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/hugoblanc/transcribe.git
cd transcribe
```

### 2. Install dependencies

**macOS:**

```bash
# Install system dependencies
brew install blackhole-2ch ffmpeg portaudio

# Run install script
./install.sh

# Activate virtual environment
source venv/bin/activate
```

**Windows:**

```batch
:: Double-click or run in terminal
install_windows.bat

:: Activate virtual environment
venv\Scripts\activate.bat
```

### 3. Configure OpenAI API key

```bash
# Linux/macOS
export OPENAI_API_KEY="your-api-key"

# Windows (PowerShell)
$env:OPENAI_API_KEY="your-api-key"

# Windows (CMD)
set OPENAI_API_KEY=your-api-key
```

Add this to your shell profile (`.bashrc`, `.zshrc`) for persistence.

### 4. Configure BlackHole (macOS only)

1. Open "Audio MIDI Setup" (Spotlight search)
2. Click "+" → "Create Multi-Output Device"
3. Check both "BlackHole 2ch" and your speakers/headphones
4. Right-click → "Use This Device For Sound Output"

### 5. Verify installation

```bash
transcribe check
```

## Usage

```bash
# Check system configuration
transcribe check

# List audio devices
transcribe devices

# Test a specific device
transcribe test-audio 3

# Start recording (Ctrl+C to stop and transcribe)
transcribe start

# With options
transcribe start --model gpt-4o-transcribe --language en
transcribe start --mic-device 1 --system-device 3

# Transcribe existing file
transcribe file recording.wav
```

## Commands

| Command | Description |
|---------|-------------|
| `transcribe check` | Verify system setup (FFmpeg, API key, audio) |
| `transcribe devices` | List audio devices |
| `transcribe test-audio <id>` | Test audio capture |
| `transcribe start` | Start recording |
| `transcribe file <path>` | Transcribe audio file |
| `transcribe info` | Show help |

## Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable verbose logging |
| `--model` | Model: `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, `whisper-1` |
| `--language` | Language code (fr/en/...) |
| `--format` | Output format (txt/json/srt) |
| `--mic-device` | Force microphone device index |
| `--system-device` | Force system audio device index |

## Troubleshooting

### No system audio captured

**Windows:**
1. Run `transcribe devices` and look for "Stereo Mix" or "WASAPI Loopback"
2. Enable "Stereo Mix" in Windows Sound settings → Recording
3. Or use `--system-device <id>` with the correct device

**macOS:**
1. Install BlackHole: `brew install blackhole-2ch`
2. Configure in Audio MIDI Setup (see above)
3. Reboot if just installed

### Testing devices

```bash
# List all devices
transcribe devices

# Test microphone (speak during test)
transcribe test-audio 1

# Test system audio (play music during test)
transcribe test-audio 3
```

### Debug mode

```bash
# Verbose output
transcribe --debug start

# Check logs
cat logs/transcribe_*.log
```

## How it works

1. **Audio Capture**: Records two separate streams
   - Microphone → your voice
   - System audio → other participants (via WASAPI on Windows, BlackHole on macOS)

2. **Transcription**: Sends audio to OpenAI API
   - Default model: `gpt-4o-mini-transcribe` (fast and cost-effective)
   - Supports `gpt-4o-transcribe` for higher quality
   - Supports `whisper-1` for detailed timestamps

3. **Speaker Diarization**: Labels segments by source
   - Microphone audio → "Moi"
   - System audio → "Interlocuteur"

## License

MIT
