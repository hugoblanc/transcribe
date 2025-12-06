"""Audio utilities for compression and chunking."""

import subprocess
import shutil
from pathlib import Path
from typing import List, Optional
import math

from .config import get_logger

# OpenAI API limit
MAX_FILE_SIZE_MB = 25
TARGET_FILE_SIZE_MB = 20  # Leave some margin

# Compression settings
MP3_BITRATE = "64k"  # Good enough for voice, small files


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available."""
    return shutil.which("ffmpeg") is not None


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using FFmpeg."""
    logger = get_logger()
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not get duration: {e}")
        return 0.0


def compress_audio(input_path: Path, output_path: Optional[Path] = None,
                   bitrate: str = MP3_BITRATE) -> Path:
    """Compress audio file to MP3.

    Args:
        input_path: Path to input audio file (WAV, etc.)
        output_path: Path for output MP3 (default: same name with .mp3)
        bitrate: MP3 bitrate (default: 64k for voice)

    Returns:
        Path to compressed MP3 file
    """
    logger = get_logger()

    if output_path is None:
        output_path = input_path.with_suffix(".mp3")

    logger.info(f"Compressing {input_path.name} to MP3 ({bitrate})...")

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",  # Overwrite
                "-i", str(input_path),
                "-vn",  # No video
                "-acodec", "libmp3lame",
                "-b:a", bitrate,
                "-ac", "1",  # Mono
                "-ar", "16000",  # 16kHz sample rate
                str(output_path)
            ],
            capture_output=True,
            check=True
        )

        input_size = input_path.stat().st_size / (1024 * 1024)
        output_size = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Compressed: {input_size:.1f}MB -> {output_size:.1f}MB")

        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else e}")
        raise RuntimeError(f"Failed to compress audio: {e}")


def split_audio(input_path: Path, chunk_duration_seconds: int = 600,
                output_dir: Optional[Path] = None) -> List[Path]:
    """Split audio file into chunks.

    Args:
        input_path: Path to input audio file
        chunk_duration_seconds: Duration of each chunk (default: 10 min)
        output_dir: Directory for output chunks (default: same as input)

    Returns:
        List of paths to chunk files
    """
    logger = get_logger()

    if output_dir is None:
        output_dir = input_path.parent

    # Get total duration
    total_duration = get_audio_duration(input_path)
    if total_duration <= 0:
        logger.warning("Could not determine duration, returning original file")
        return [input_path]

    # Calculate number of chunks
    num_chunks = math.ceil(total_duration / chunk_duration_seconds)

    if num_chunks <= 1:
        logger.debug("File is short enough, no splitting needed")
        return [input_path]

    logger.info(f"Splitting {input_path.name} into {num_chunks} chunks...")

    chunks = []
    base_name = input_path.stem
    suffix = input_path.suffix

    for i in range(num_chunks):
        start_time = i * chunk_duration_seconds
        chunk_path = output_dir / f"{base_name}_chunk{i+1:02d}{suffix}"

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i", str(input_path),
                    "-ss", str(start_time),
                    "-t", str(chunk_duration_seconds),
                    "-acodec", "copy",  # No re-encoding
                    str(chunk_path)
                ],
                capture_output=True,
                check=True
            )
            chunks.append(chunk_path)
            logger.debug(f"Created chunk: {chunk_path.name}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create chunk {i+1}: {e}")
            raise

    return chunks


def prepare_for_api(audio_path: Path, max_size_mb: float = TARGET_FILE_SIZE_MB) -> List[Path]:
    """Prepare audio file(s) for API upload.

    Compresses to MP3 and splits if necessary.

    Args:
        audio_path: Path to input audio file
        max_size_mb: Maximum file size in MB

    Returns:
        List of paths ready for API upload
    """
    logger = get_logger()

    if not check_ffmpeg():
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

    # Compress to MP3
    mp3_path = compress_audio(audio_path)

    # Check size
    file_size_mb = mp3_path.stat().st_size / (1024 * 1024)
    logger.info(f"Compressed file size: {file_size_mb:.1f} MB")

    if file_size_mb <= max_size_mb:
        return [mp3_path]

    # Need to split
    # Calculate chunk duration based on file size
    duration = get_audio_duration(mp3_path)
    mb_per_second = file_size_mb / duration if duration > 0 else 0.01
    chunk_duration = int(max_size_mb / mb_per_second * 0.9)  # 90% margin
    chunk_duration = max(300, min(chunk_duration, 900))  # 5-15 minutes

    logger.info(f"File too large, splitting into {chunk_duration}s chunks...")

    return split_audio(mp3_path, chunk_duration)
