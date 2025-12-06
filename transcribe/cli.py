"""Command-line interface for Transcribe."""

import click
import signal
import sys
import time
from pathlib import Path
from datetime import datetime

from .config import setup_logging, get_platform_info, IS_WINDOWS, IS_MAC
from .recorder import (
    DualAudioRecorder,
    check_system_audio_available,
    test_audio_capture
)
from .transcriber import MeetingTranscriber, get_available_models, recommend_model, check_api_key
from .audio_utils import check_ffmpeg
from .output_formatter import save_transcript, format_timestamp


# Global recorder for signal handling
_recorder: DualAudioRecorder = None


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx, debug):
    """Transcribe - Cross-platform meeting transcription tool.

    Captures audio from your microphone and system audio,
    then transcribes using OpenAI Whisper.

    Works on Windows (WASAPI) and macOS (BlackHole).
    """
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug
    setup_logging(debug=debug)


@cli.command()
@click.option('--model', '-m', default=None,
              type=click.Choice(get_available_models()),
              help='Whisper model (default: auto)')
@click.option('--language', '-l', default='fr',
              help='Language code (default: fr)')
@click.option('--format', '-f', 'output_format', default='txt',
              type=click.Choice(['txt', 'json', 'srt']),
              help='Output format (default: txt)')
@click.option('--output-dir', '-o', default='transcripts',
              help='Output directory')
@click.option('--mic-device', type=int, default=None,
              help='Microphone device index (use "transcribe devices" to list)')
@click.option('--system-device', type=int, default=None,
              help='System audio device index')
@click.pass_context
def start(ctx, model, language, output_format, output_dir, mic_device, system_device):
    """Start recording a meeting.

    Press Ctrl+C to stop recording and start transcription.

    Examples:
        transcribe start
        transcribe start --model small --language en
        transcribe start --mic-device 1 --system-device 3
    """
    global _recorder
    debug = ctx.obj.get('debug', False)

    # Check system audio
    if not check_system_audio_available():
        if IS_MAC:
            click.echo(click.style("Warning: BlackHole not found!", fg='yellow'))
            click.echo("Install: brew install blackhole-2ch")
            click.echo("Then configure in Audio MIDI Setup.\n")
        elif IS_WINDOWS:
            click.echo(click.style("Warning: No loopback device found!", fg='yellow'))
            click.echo("Try enabling 'Stereo Mix' in Windows Sound settings.")
            click.echo("Or use --system-device to specify manually.\n")

    # Select model
    if model is None:
        model = recommend_model()
        click.echo(f"Auto-selected model: {model}")

    # Create recorder
    _recorder = DualAudioRecorder()

    # Setup signal handler
    def signal_handler(sig, frame):
        click.echo("\n\nStopping recording...")
        _stop_and_transcribe(model, language, output_format, output_dir, debug)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Header
    click.echo("\n" + "=" * 50)
    click.echo("  TRANSCRIBE - Meeting Recording")
    click.echo("=" * 50)

    # Start recording
    if not _recorder.start_recording(mic_index=mic_device, system_index=system_device):
        click.echo(click.style("\nFailed to start recording!", fg='red'))
        click.echo("\nTroubleshooting:")
        click.echo("  1. Run 'transcribe devices' to see available devices")
        click.echo("  2. Run 'transcribe test-audio <device_id>' to test a device")
        click.echo("  3. Use --mic-device and --system-device to specify devices")
        sys.exit(1)

    click.echo(click.style("\n[Recording started]", fg='green'))
    click.echo("Press Ctrl+C to stop and transcribe\n")

    # Display timer
    start_time = time.time()
    try:
        while True:
            elapsed = time.time() - start_time
            click.echo(f"\r  Recording: {format_timestamp(elapsed)}", nl=False)
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def _stop_and_transcribe(model: str, language: str,
                         output_format: str, output_dir: str, debug: bool):
    """Stop recording and run transcription."""
    global _recorder

    if _recorder is None:
        return

    # Stop recording
    mic_path, system_path = _recorder.stop_recording()

    if mic_path is None and system_path is None:
        click.echo(click.style("No audio was recorded!", fg='yellow'))
        return

    # Transcribe
    click.echo("\n" + "-" * 50)
    click.echo("Starting transcription...")
    click.echo("-" * 50 + "\n")

    try:
        transcriber = MeetingTranscriber(model_name=model)
        segments = transcriber.transcribe_meeting(
            mic_path=mic_path,
            system_path=system_path,
            language=language
        )

        if not segments:
            click.echo(click.style("No speech detected!", fg='yellow'))
            return

        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = save_transcript(
            segments=segments,
            output_dir=Path(output_dir),
            base_name=f"meeting_{timestamp}",
            format=output_format,
            model_name=f"whisper-{model}"
        )

        click.echo("\n" + "=" * 50)
        click.echo(click.style(f"  Transcript saved: {output_path}", fg='green'))
        click.echo(f"  Segments: {len(segments)}")
        click.echo("=" * 50 + "\n")

    except Exception as e:
        click.echo(click.style(f"\nTranscription error: {e}", fg='red'))
        if debug:
            import traceback
            traceback.print_exc()


@cli.command()
def devices():
    """List all available audio devices.

    Shows device index, name, channels, and audio API.
    Use the device index with --mic-device or --system-device options.
    """
    recorder = DualAudioRecorder()
    recorder.list_devices()

    # Show auto-detected devices
    mic, system = recorder.find_devices()

    click.echo("Auto-detected devices:")
    if mic:
        click.echo(click.style(f"  Microphone: [{mic.index}] {mic.name}", fg='green'))
    else:
        click.echo(click.style("  Microphone: Not found", fg='red'))

    if system:
        click.echo(click.style(f"  System:     [{system.index}] {system.name}", fg='green'))
    else:
        click.echo(click.style("  System:     Not found", fg='yellow'))
        if IS_WINDOWS:
            click.echo("\n  Tip: Enable 'Stereo Mix' in Windows Sound settings")
            click.echo("       or look for a WASAPI loopback device above.")
        elif IS_MAC:
            click.echo("\n  Tip: Install BlackHole: brew install blackhole-2ch")

    click.echo("")


@cli.command('test-audio')
@click.argument('device_id', type=int)
@click.option('--duration', '-d', default=3.0, help='Test duration in seconds')
def test_audio(device_id, duration):
    """Test audio capture from a specific device.

    Records for a few seconds and shows audio levels.
    Use this to verify a device is working before recording.

    Example:
        transcribe test-audio 3
        transcribe test-audio 5 --duration 5
    """
    click.echo(f"\nTesting device {device_id}...")
    click.echo("Make some noise or play audio!\n")

    success = test_audio_capture(device_id, duration)

    if success:
        click.echo(click.style("\nDevice is working!", fg='green'))
    else:
        click.echo(click.style("\nNo audio detected. Check:", fg='yellow'))
        click.echo("  - Is the device enabled?")
        click.echo("  - Is audio actually playing/speaking?")
        click.echo("  - Try a different device index")


@cli.command()
@click.pass_context
def check(ctx):
    """Check system requirements and configuration.

    Verifies FFmpeg, OpenAI API key, and audio devices.
    """
    debug = ctx.obj.get('debug', False)

    click.echo("\n" + "=" * 50)
    click.echo("  SYSTEM CHECK")
    click.echo("=" * 50 + "\n")

    info = get_platform_info()
    all_ok = True

    # Platform
    click.echo(f"Platform: {info['os']} ({info['machine']})")
    click.echo(f"Python:   {info['python_version']}")

    # FFmpeg
    click.echo("")
    if check_ffmpeg():
        click.echo(click.style("FFmpeg:       OK", fg='green'))
    else:
        click.echo(click.style("FFmpeg:       NOT FOUND", fg='red'))
        click.echo("              Install: winget install ffmpeg (Windows)")
        click.echo("              Install: brew install ffmpeg (macOS)")
        all_ok = False

    # OpenAI API Key
    if check_api_key():
        click.echo(click.style("OpenAI API:   OK (OPENAI_API_KEY set)", fg='green'))
    else:
        click.echo(click.style("OpenAI API:   NOT CONFIGURED", fg='red'))
        click.echo("              Set OPENAI_API_KEY environment variable")
        all_ok = False

    # Audio
    click.echo("")
    if check_system_audio_available():
        click.echo(click.style("System audio: Available", fg='green'))
    else:
        click.echo(click.style("System audio: Not found", fg='yellow'))
        if IS_WINDOWS:
            click.echo("              Enable 'Stereo Mix' or use VB-Cable")
        elif IS_MAC:
            click.echo("              Install BlackHole: brew install blackhole-2ch")

    # Summary
    click.echo("")
    if all_ok:
        click.echo(click.style("Ready to transcribe!", fg='green'))
    else:
        click.echo(click.style("Some requirements missing (see above)", fg='yellow'))

    click.echo(f"\nModel: {recommend_model()}")
    click.echo("=" * 50 + "\n")

    if debug:
        click.echo("Full platform info:")
        for k, v in info.items():
            click.echo(f"  {k}: {v}")
        click.echo("")


@cli.command()
@click.argument('audio_file', type=click.Path(exists=True))
@click.option('--model', '-m', default='medium',
              type=click.Choice(get_available_models()))
@click.option('--language', '-l', default='fr')
@click.option('--format', '-f', 'output_format', default='txt',
              type=click.Choice(['txt', 'json', 'srt']))
@click.option('--output-dir', '-o', default='transcripts')
@click.pass_context
def file(ctx, audio_file, model, language, output_format, output_dir):
    """Transcribe an existing audio file.

    Example:
        transcribe file recording.wav
        transcribe file meeting.mp3 --model large --language en
    """
    debug = ctx.obj.get('debug', False)
    audio_path = Path(audio_file)

    click.echo(f"\nTranscribing: {audio_path.name}")
    click.echo(f"Model: {model}, Language: {language}\n")

    try:
        transcriber = MeetingTranscriber(model_name=model)
        result = transcriber.transcribe_audio(audio_path, language)

        from .transcriber import Segment
        segments = [
            Segment(
                speaker="Speaker",
                start=seg["start"],
                end=seg["end"],
                text=seg["text"].strip()
            )
            for seg in result.get("segments", [])
            if seg.get("text", "").strip()
        ]

        if not segments:
            click.echo(click.style("No speech detected!", fg='yellow'))
            return

        output_path = save_transcript(
            segments=segments,
            output_dir=Path(output_dir),
            base_name=audio_path.stem,
            format=output_format,
            model_name=f"whisper-{model}"
        )

        click.echo(click.style(f"\nSaved: {output_path}", fg='green'))

    except Exception as e:
        click.echo(click.style(f"\nError: {e}", fg='red'))
        if debug:
            import traceback
            traceback.print_exc()


@cli.command()
def info():
    """Show installation and usage information."""
    click.echo("""
TRANSCRIBE - Meeting Transcription Tool
========================================

INSTALLATION (Windows):
  1. Install Python 3.9+
  2. pip install -e .
  3. That's it! WASAPI loopback is built into Windows.

INSTALLATION (macOS):
  1. brew install blackhole-2ch ffmpeg portaudio
  2. pip install -e .
  3. Configure BlackHole in Audio MIDI Setup

USAGE:
  transcribe devices      # List audio devices
  transcribe check        # Verify setup
  transcribe test-audio 3 # Test device #3
  transcribe start        # Start recording
  transcribe file a.wav   # Transcribe existing file

OPTIONS:
  --debug                 # Show detailed logs
  --model small/medium    # Whisper model size
  --language en/fr/...    # Audio language
  --mic-device N          # Force microphone device
  --system-device N       # Force system audio device

TROUBLESHOOTING:
  1. No system audio? Run 'transcribe devices' and look for
     loopback/stereo mix devices.
  2. Test devices with 'transcribe test-audio <id>'
  3. Check logs in ./logs/ folder
  4. Use --debug flag for verbose output
""")


if __name__ == '__main__':
    cli()
