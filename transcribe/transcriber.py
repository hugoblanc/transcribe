"""Transcription module using OpenAI Whisper."""

import whisper
import torch
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Segment:
    """A transcription segment with speaker and timing info."""
    speaker: str
    start: float
    end: float
    text: str


class MeetingTranscriber:
    """Transcribes meeting audio using Whisper with speaker diarization."""

    # Available models (smallest to largest)
    MODELS = ["tiny", "base", "small", "medium", "large"]

    def __init__(self, model_name: str = "medium", device: Optional[str] = None):
        """Initialize the transcriber.

        Args:
            model_name: Whisper model to use (tiny, base, small, medium, large)
            device: Device to use (None for auto-detect, 'cpu', 'cuda', 'mps')
        """
        self.model_name = model_name

        # Auto-detect device
        if device is None:
            if torch.backends.mps.is_available():
                device = "mps"  # Apple Silicon GPU
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"

        self.device = device
        self.model = None

    def load_model(self) -> None:
        """Load the Whisper model."""
        print(f"Loading Whisper model '{self.model_name}' on {self.device}...")

        # Note: Whisper loads to CPU first, then we can move to device
        self.model = whisper.load_model(self.model_name)

        if self.device == "mps":
            # For MPS, we keep the model but transcription will use fp32
            pass
        elif self.device == "cuda":
            self.model = self.model.to(self.device)

        print(f"Model loaded successfully")

    def transcribe_audio(self, audio_path: Path, language: str = "fr") -> Dict[str, Any]:
        """Transcribe a single audio file.

        Args:
            audio_path: Path to the audio file
            language: Language code (e.g., 'fr', 'en')

        Returns:
            Whisper transcription result with segments
        """
        if self.model is None:
            self.load_model()

        result = self.model.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,
            verbose=False,
            fp16=False  # Use fp32 for MPS compatibility
        )

        return result

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
                # Skip empty or very short segments
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

        # Merge consecutive segments from the same speaker
        segments = self._merge_consecutive_segments(segments)

        return segments

    def _merge_consecutive_segments(self, segments: List[Segment],
                                    gap_threshold: float = 1.0) -> List[Segment]:
        """Merge consecutive segments from the same speaker.

        Args:
            segments: List of segments sorted by start time
            gap_threshold: Maximum gap (seconds) to merge segments

        Returns:
            Merged list of segments
        """
        if not segments:
            return segments

        merged: List[Segment] = []
        current = segments[0]

        for next_seg in segments[1:]:
            # Check if same speaker and close enough in time
            same_speaker = current.speaker == next_seg.speaker
            gap = next_seg.start - current.end

            if same_speaker and gap < gap_threshold:
                # Merge segments
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
    """Get list of available Whisper models."""
    return MeetingTranscriber.MODELS


def recommend_model() -> str:
    """Recommend a model based on available hardware."""
    if torch.backends.mps.is_available():
        # Apple Silicon - medium works well
        return "medium"
    elif torch.cuda.is_available():
        # NVIDIA GPU - can handle larger models
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        if vram >= 10:
            return "large"
        elif vram >= 5:
            return "medium"
        else:
            return "small"
    else:
        # CPU only - use smaller model
        return "small"
