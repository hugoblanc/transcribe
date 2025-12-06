"""Transcription module using OpenAI API."""

import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from .config import get_logger
from .audio_utils import prepare_for_api, check_ffmpeg


@dataclass
class Segment:
    """A transcription segment with speaker and timing info."""
    speaker: str
    start: float
    end: float
    text: str


class MeetingTranscriber:
    """Transcribes meeting audio using OpenAI API."""

    MODELS = ["gpt-4o-transcribe", "gpt-4o-mini-transcribe", "whisper-1"]

    def __init__(self, model_name: str = "gpt-4o-mini-transcribe", api_key: Optional[str] = None):
        """Initialize the transcriber.

        Args:
            model_name: OpenAI model to use
            api_key: OpenAI API key (default: from OPENAI_API_KEY env var)
        """
        self.model_name = model_name
        self.logger = get_logger()

        # Get API key
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Initialize OpenAI client
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")

        self.logger.info(f"Using model: {model_name}")

    def transcribe_audio(self, audio_path: Path, language: str = "fr") -> dict:
        """Transcribe a single audio file.

        Args:
            audio_path: Path to the audio file
            language: Language code (e.g., 'fr', 'en')

        Returns:
            Transcription result with text and segments
        """
        self.logger.info(f"Transcribing: {audio_path.name}")

        # Prepare file (compress + split if needed)
        if not check_ffmpeg():
            raise RuntimeError("FFmpeg required for audio processing")

        files_to_transcribe = prepare_for_api(audio_path)
        self.logger.info(f"Prepared {len(files_to_transcribe)} file(s) for transcription")

        all_segments = []
        time_offset = 0.0

        for file_path in files_to_transcribe:
            self.logger.debug(f"Sending to API: {file_path.name}")

            with open(file_path, "rb") as audio_file:
                # Use the appropriate API based on model
                if self.model_name == "whisper-1":
                    response = self.client.audio.transcriptions.create(
                        model=self.model_name,
                        file=audio_file,
                        language=language,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"]
                    )
                else:
                    # gpt-4o-transcribe models
                    response = self.client.audio.transcriptions.create(
                        model=self.model_name,
                        file=audio_file,
                        language=language,
                        response_format="verbose_json"
                    )

            # Process segments
            if hasattr(response, 'segments') and response.segments:
                for seg in response.segments:
                    all_segments.append({
                        "start": seg.start + time_offset,
                        "end": seg.end + time_offset,
                        "text": seg.text.strip()
                    })
                # Update offset for next chunk
                if response.segments:
                    time_offset = all_segments[-1]["end"]
            else:
                # No segments, just full text
                all_segments.append({
                    "start": time_offset,
                    "end": time_offset + 60,  # Estimate
                    "text": response.text.strip()
                })
                time_offset += 60

        return {
            "text": " ".join(seg["text"] for seg in all_segments),
            "segments": all_segments
        }

    def transcribe_meeting(self, mic_path: Path, system_path: Path,
                           language: str = "fr",
                           mic_label: str = "Moi",
                           system_label: str = "Interlocuteur") -> List[Segment]:
        """Transcribe both audio sources and merge by timestamp.

        Args:
            mic_path: Path to microphone audio file
            system_path: Path to system audio file
            language: Language code
            mic_label: Label for microphone speaker
            system_label: Label for system speaker

        Returns:
            List of Segment objects sorted by start time
        """
        segments: List[Segment] = []

        # Transcribe microphone audio
        if mic_path and mic_path.exists():
            print(f"Transcribing microphone audio...")
            mic_result = self.transcribe_audio(mic_path, language)

            for seg in mic_result.get("segments", []):
                text = seg.get("text", "").strip()
                if text and len(text) > 1:
                    segments.append(Segment(
                        speaker=mic_label,
                        start=seg["start"],
                        end=seg["end"],
                        text=text
                    ))

        # Transcribe system audio
        if system_path and system_path.exists():
            print(f"Transcribing system audio...")
            system_result = self.transcribe_audio(system_path, language)

            for seg in system_result.get("segments", []):
                text = seg.get("text", "").strip()
                if text and len(text) > 1:
                    segments.append(Segment(
                        speaker=system_label,
                        start=seg["start"],
                        end=seg["end"],
                        text=text
                    ))

        # Sort by start time
        segments.sort(key=lambda s: s.start)

        # Merge consecutive segments from same speaker
        segments = self._merge_consecutive_segments(segments)

        return segments

    def _merge_consecutive_segments(self, segments: List[Segment],
                                    gap_threshold: float = 1.0) -> List[Segment]:
        """Merge consecutive segments from the same speaker."""
        if not segments:
            return segments

        merged: List[Segment] = []
        current = segments[0]

        for next_seg in segments[1:]:
            same_speaker = current.speaker == next_seg.speaker
            gap = next_seg.start - current.end

            if same_speaker and gap < gap_threshold:
                current = Segment(
                    speaker=current.speaker,
                    start=current.start,
                    end=next_seg.end,
                    text=f"{current.text} {next_seg.text}"
                )
            else:
                merged.append(current)
                current = next_seg

        merged.append(current)
        return merged


def get_available_models() -> List[str]:
    """Get list of available models."""
    return MeetingTranscriber.MODELS


def recommend_model() -> str:
    """Recommend a model."""
    # gpt-4o-mini-transcribe is fast and cheap
    return "gpt-4o-mini-transcribe"


def check_api_key() -> bool:
    """Check if OpenAI API key is configured."""
    return bool(os.environ.get("OPENAI_API_KEY"))
