"""Output formatting module for transcripts."""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from .transcriber import Segment


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def calculate_duration(segments: List[Segment]) -> float:
    """Calculate total duration from segments."""
    if not segments:
        return 0.0
    return max(seg.end for seg in segments)


def save_as_txt(segments: List[Segment], output_path: Path,
                model_name: str = "whisper") -> None:
    """Save transcript as plain text file.

    Format:
    [HH:MM:SS] Speaker: Text content...
    """
    duration = calculate_duration(segments)
    now = datetime.now()

    with open(output_path, 'w', encoding='utf-8') as f:
        # Header
        f.write(f"TRANSCRIPTION - {now.strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 50 + "\n\n")

        # Segments
        for seg in segments:
            timestamp = format_timestamp(seg.start)
            f.write(f"[{timestamp}] {seg.speaker}: {seg.text}\n\n")

        # Footer
        f.write("-" * 50 + "\n")
        f.write(f"Duration: {format_timestamp(duration)}\n")
        f.write(f"Model: {model_name}\n")
        f.write(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")


def save_as_json(segments: List[Segment], output_path: Path,
                 model_name: str = "whisper") -> None:
    """Save transcript as JSON file."""
    duration = calculate_duration(segments)
    now = datetime.now()

    data = {
        "metadata": {
            "date": now.isoformat(),
            "duration": duration,
            "model": model_name,
            "segment_count": len(segments)
        },
        "segments": [
            {
                "speaker": seg.speaker,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            for seg in segments
        ]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_as_srt(segments: List[Segment], output_path: Path) -> None:
    """Save transcript as SRT subtitle file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, start=1):
            start_ts = format_srt_timestamp(seg.start)
            end_ts = format_srt_timestamp(seg.end)

            f.write(f"{i}\n")
            f.write(f"{start_ts} --> {end_ts}\n")
            f.write(f"[{seg.speaker}] {seg.text}\n")
            f.write("\n")


def save_transcript(segments: List[Segment], output_dir: Path,
                    base_name: str, format: str = "txt",
                    model_name: str = "whisper") -> Path:
    """Save transcript in the specified format.

    Args:
        segments: List of transcript segments
        output_dir: Directory to save the file
        base_name: Base filename (without extension)
        format: Output format ('txt', 'json', 'srt')
        model_name: Name of the model used for transcription

    Returns:
        Path to the saved file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if format == "txt":
        output_path = output_dir / f"{base_name}.txt"
        save_as_txt(segments, output_path, model_name)
    elif format == "json":
        output_path = output_dir / f"{base_name}.json"
        save_as_json(segments, output_path, model_name)
    elif format == "srt":
        output_path = output_dir / f"{base_name}.srt"
        save_as_srt(segments, output_path)
    else:
        raise ValueError(f"Unsupported format: {format}")

    return output_path
