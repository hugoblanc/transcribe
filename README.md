# Transcribe

CLI tool for transcribing meetings with speaker diarization. Captures both your microphone and system audio (what you hear), then transcribes using OpenAI Whisper.

**Works on Windows and macOS.**

## Features

- Dual audio capture (mic + system audio)
- Automatic speaker labeling ("Me" vs "Other")
- Local transcription with Whisper (no cloud, free)
- Multiple output formats (TXT, JSON, SRT)
- Debug tools for troubleshooting

## Quick Start

### Windows

```batch
# Clone the repo
git clone https://github.com/YOUR_USERNAME/transcribe.git
cd transcribe

# Install (double-click or run in terminal)
install_windows.bat

# Activate and run
venv\Scripts\activate.bat
transcribe check
transcribe start
```

### macOS

```bash
# Install dependencies
brew install blackhole-2ch ffmpeg portaudio

# Clone and install
git clone https://github.com/YOUR_USERNAME/transcribe.git
cd transcribe
./install.sh

# Configure BlackHole in Audio MIDI Setup (see below)

# Run
source venv/bin/activate
transcribe start
```

#### BlackHole Setup (macOS only)

1. Open "Audio MIDI Setup" (Spotlight search)
2. Click "+" → "Create Multi-Output Device"
3. Check both "BlackHole 2ch" and your speakers/headphones
4. Right-click → "Use This Device For Sound Output"

## Usage

```bash
# Check system configuration
transcribe check

# List audio devices
transcribe devices

# Test a specific device
transcribe test-audio 3

# Start recording (Ctrl+C to stop)
transcribe start

# With options
transcribe start --model small --language en
transcribe start --mic-device 1 --system-device 3

# Transcribe existing file
transcribe file recording.wav
```

## Commands

| Command | Description |
|---------|-------------|
| `transcribe check` | Verify system setup |
| `transcribe devices` | List audio devices |
| `transcribe test-audio <id>` | Test audio capture |
| `transcribe start` | Start recording |
| `transcribe file <path>` | Transcribe audio file |
| `transcribe info` | Show help |

## Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable verbose logging |
| `--model` | Whisper model (tiny/small/medium/large) |
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

2. **Transcription**: Uses OpenAI Whisper locally
   - No cloud, no API costs
   - Runs on CPU or GPU (Apple Silicon, NVIDIA)

3. **Speaker Diarization**: Labels segments by source
   - Microphone audio → "Me"
   - System audio → "Other"

## Requirements

- Python 3.9+
- ~2GB disk space (for Whisper model)
- macOS 12+ or Windows 10+

## License

MIT
