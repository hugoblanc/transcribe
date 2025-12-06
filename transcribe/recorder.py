"""Cross-platform audio recorder for capturing microphone and system audio.

Supports:
- Windows: WASAPI loopback (native, no driver needed)
- macOS: BlackHole virtual audio driver
"""

import sounddevice as sd
import numpy as np
from scipy.io import wavfile
from scipy import signal as scipy_signal
from datetime import datetime
from pathlib import Path
import threading
import queue
import time
from typing import Optional, Tuple, List
from dataclasses import dataclass

from .config import (
    IS_WINDOWS, IS_MAC,
    SAMPLE_RATE, CHANNELS, BLOCK_SIZE,
    RECORDINGS_DIR, get_logger
)

# Target sample rate for Whisper
WHISPER_SAMPLE_RATE = 16000


@dataclass
class AudioDevice:
    """Represents an audio device."""
    index: int
    name: str
    channels: int
    is_loopback: bool = False
    hostapi: str = ""


class DualAudioRecorder:
    """Records audio from both microphone and system audio.

    On Windows: Uses WASAPI loopback for system audio
    On macOS: Uses BlackHole virtual audio driver
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, output_dir: str = None):
        self.target_sample_rate = WHISPER_SAMPLE_RATE  # For output files
        self.recording_sample_rate = sample_rate  # Will be adjusted per device
        self.output_dir = Path(output_dir) if output_dir else RECORDINGS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.logger = get_logger()
        self.is_recording = False
        self.start_time: Optional[float] = None

        # Audio buffers
        self.mic_queue: queue.Queue = queue.Queue()
        self.system_queue: queue.Queue = queue.Queue()

        # Streams
        self.mic_stream: Optional[sd.InputStream] = None
        self.system_stream: Optional[sd.InputStream] = None

        # Device info
        self.mic_device: Optional[AudioDevice] = None
        self.system_device: Optional[AudioDevice] = None

        # Actual sample rates used (may differ per device)
        self.mic_sample_rate: int = sample_rate
        self.system_sample_rate: int = sample_rate

        self.logger.debug(f"Platform: {'Windows' if IS_WINDOWS else 'macOS' if IS_MAC else 'Linux'}")
        self.logger.debug(f"Target sample rate: {self.target_sample_rate} Hz")
        self.logger.debug(f"Output dir: {self.output_dir}")

    def get_all_devices(self) -> List[AudioDevice]:
        """Get all available audio devices with detailed info."""
        devices = []
        sd_devices = sd.query_devices()
        hostapis = sd.query_hostapis()

        for i, dev in enumerate(sd_devices):
            if dev['max_input_channels'] > 0:
                hostapi_name = hostapis[dev['hostapi']]['name']

                # Check if it's a loopback device (Windows WASAPI)
                is_loopback = False
                if IS_WINDOWS and 'WASAPI' in hostapi_name:
                    # Loopback devices often have "Loopback" in name or are output devices
                    # appearing as input in WASAPI
                    is_loopback = 'loopback' in dev['name'].lower()

                devices.append(AudioDevice(
                    index=i,
                    name=dev['name'],
                    channels=dev['max_input_channels'],
                    is_loopback=is_loopback,
                    hostapi=hostapi_name
                ))

        return devices

    def list_devices(self) -> None:
        """Print all available audio devices."""
        devices = self.get_all_devices()

        print("\n" + "=" * 70)
        print("  AVAILABLE AUDIO DEVICES")
        print("=" * 70)

        for dev in devices:
            loopback_tag = " [LOOPBACK]" if dev.is_loopback else ""
            print(f"  [{dev.index:2d}] {dev.name}")
            print(f"       Channels: {dev.channels}, API: {dev.hostapi}{loopback_tag}")

        print("=" * 70 + "\n")

    def find_devices(self) -> Tuple[Optional[AudioDevice], Optional[AudioDevice]]:
        """Auto-detect microphone and system audio devices.

        Returns:
            Tuple of (mic_device, system_device)
        """
        devices = self.get_all_devices()
        mic_device = None
        system_device = None

        self.logger.debug(f"Searching among {len(devices)} input devices...")

        if IS_WINDOWS:
            # Windows: Look for WASAPI devices
            wasapi_devices = [d for d in devices if 'WASAPI' in d.hostapi]
            self.logger.debug(f"Found {len(wasapi_devices)} WASAPI devices")

            for dev in wasapi_devices:
                name_lower = dev.name.lower()

                # System audio: look for loopback or speaker/output as input
                if system_device is None:
                    if dev.is_loopback or 'loopback' in name_lower:
                        system_device = dev
                        self.logger.debug(f"Found system loopback: {dev.name}")
                    elif any(x in name_lower for x in ['speaker', 'output', 'realtek', 'stereo mix']):
                        system_device = dev
                        self.logger.debug(f"Found potential system audio: {dev.name}")

                # Microphone
                if mic_device is None:
                    if any(x in name_lower for x in ['microphone', 'mic', 'headset']):
                        if not dev.is_loopback:
                            mic_device = dev
                            self.logger.debug(f"Found microphone: {dev.name}")

        elif IS_MAC:
            # macOS: Look for BlackHole and built-in mic
            for dev in devices:
                name_lower = dev.name.lower()

                # System audio via BlackHole
                if system_device is None and 'blackhole' in name_lower:
                    system_device = dev
                    self.logger.debug(f"Found BlackHole: {dev.name}")

                # Microphone
                if mic_device is None:
                    if any(x in name_lower for x in ['macbook', 'built-in', 'microphone']):
                        mic_device = dev
                        self.logger.debug(f"Found microphone: {dev.name}")

        # Fallback: use default input device for mic
        if mic_device is None:
            try:
                default_idx = sd.default.device[0]
                if default_idx is not None and default_idx >= 0:
                    for dev in devices:
                        if dev.index == default_idx:
                            mic_device = dev
                            self.logger.debug(f"Using default input as mic: {dev.name}")
                            break
            except Exception as e:
                self.logger.warning(f"Could not get default device: {e}")

        return mic_device, system_device

    def _create_callback(self, audio_queue: queue.Queue, name: str):
        """Create a callback function for audio stream."""
        def callback(indata, frames, time_info, status):
            if status:
                self.logger.warning(f"{name} stream status: {status}")
            audio_queue.put(indata.copy())
        return callback

    def _get_device_sample_rate(self, device_index: int) -> int:
        """Get the default sample rate for a device."""
        try:
            device_info = sd.query_devices(device_index)
            default_sr = int(device_info['default_samplerate'])
            self.logger.debug(f"Device {device_index} default sample rate: {default_sr}")
            return default_sr
        except Exception as e:
            self.logger.warning(f"Could not get sample rate for device {device_index}: {e}")
            return 44100  # Common fallback

    def start_recording(self, mic_index: Optional[int] = None,
                        system_index: Optional[int] = None) -> bool:
        """Start recording from both audio sources.

        Args:
            mic_index: Device index for microphone (auto-detect if None)
            system_index: Device index for system audio (auto-detect if None)

        Returns:
            True if recording started successfully
        """
        # Find devices
        if mic_index is None or system_index is None:
            auto_mic, auto_system = self.find_devices()

            if mic_index is not None:
                # Manual mic index, convert to AudioDevice
                devices = self.get_all_devices()
                self.mic_device = next((d for d in devices if d.index == mic_index), None)
            else:
                self.mic_device = auto_mic

            if system_index is not None:
                devices = self.get_all_devices()
                self.system_device = next((d for d in devices if d.index == system_index), None)
            else:
                self.system_device = auto_system
        else:
            devices = self.get_all_devices()
            self.mic_device = next((d for d in devices if d.index == mic_index), None)
            self.system_device = next((d for d in devices if d.index == system_index), None)

        # Validate
        if self.mic_device is None:
            self.logger.error("No microphone device found!")
            print("\nError: No microphone found.")
            print("Use 'transcribe devices' to list available devices.")
            print("Then use 'transcribe start --mic-device <index>'")
            return False

        if self.system_device is None:
            self.logger.warning("No system audio device found!")
            if IS_MAC:
                print("\nWarning: BlackHole not found.")
                print("Install it with: brew install blackhole-2ch")
                print("Then configure in Audio MIDI Setup.")
            elif IS_WINDOWS:
                print("\nWarning: No WASAPI loopback device found.")
                print("Enable 'Stereo Mix' in Windows Sound settings,")
                print("or use 'transcribe devices' to find the correct device.")

            # Continue with mic only
            print("\nContinuing with microphone only...\n")

        # Log selected devices
        print("\nUsing devices:")
        print(f"  Microphone: [{self.mic_device.index}] {self.mic_device.name}")
        if self.system_device:
            print(f"  System:     [{self.system_device.index}] {self.system_device.name}")
        else:
            print("  System:     (not available)")

        self.logger.info(f"Mic device: {self.mic_device}")
        self.logger.info(f"System device: {self.system_device}")

        # Clear queues
        while not self.mic_queue.empty():
            self.mic_queue.get()
        while not self.system_queue.empty():
            self.system_queue.get()

        try:
            # Get native sample rates for devices
            self.mic_sample_rate = self._get_device_sample_rate(self.mic_device.index)

            # Start microphone stream
            self.logger.debug(f"Opening mic stream on device {self.mic_device.index} at {self.mic_sample_rate}Hz...")
            self.mic_stream = sd.InputStream(
                device=self.mic_device.index,
                channels=CHANNELS,
                samplerate=self.mic_sample_rate,
                blocksize=BLOCK_SIZE,
                callback=self._create_callback(self.mic_queue, "Mic")
            )
            self.mic_stream.start()
            self.logger.debug("Mic stream started")

            # Start system audio stream (if available)
            if self.system_device:
                self.system_sample_rate = self._get_device_sample_rate(self.system_device.index)

                self.logger.debug(f"Opening system stream on device {self.system_device.index} at {self.system_sample_rate}Hz...")
                self.system_stream = sd.InputStream(
                    device=self.system_device.index,
                    channels=CHANNELS,
                    samplerate=self.system_sample_rate,
                    blocksize=BLOCK_SIZE,
                    callback=self._create_callback(self.system_queue, "System")
                )
                self.system_stream.start()
                self.logger.debug("System stream started")

            self.is_recording = True
            self.start_time = time.time()
            self.logger.info("Recording started")

            return True

        except Exception as e:
            self.logger.exception(f"Error starting recording: {e}")
            print(f"\nError: {e}")
            self._cleanup_streams()
            return False

    def _cleanup_streams(self):
        """Clean up audio streams."""
        if self.mic_stream:
            try:
                self.mic_stream.stop()
                self.mic_stream.close()
            except Exception as e:
                self.logger.warning(f"Error closing mic stream: {e}")
            self.mic_stream = None

        if self.system_stream:
            try:
                self.system_stream.stop()
                self.system_stream.close()
            except Exception as e:
                self.logger.warning(f"Error closing system stream: {e}")
            self.system_stream = None

    def stop_recording(self) -> Tuple[Optional[Path], Optional[Path]]:
        """Stop recording and save audio files.

        Returns:
            Tuple of (mic_path, system_path)
        """
        self.is_recording = False
        duration = time.time() - self.start_time if self.start_time else 0

        self.logger.info(f"Stopping recording after {duration:.1f}s")

        # Stop streams
        self._cleanup_streams()

        # Collect recorded data
        mic_data = []
        system_data = []

        while not self.mic_queue.empty():
            mic_data.append(self.mic_queue.get())

        while not self.system_queue.empty():
            system_data.append(self.system_queue.get())

        self.logger.debug(f"Collected {len(mic_data)} mic blocks, {len(system_data)} system blocks")

        if not mic_data and not system_data:
            self.logger.warning("No audio data recorded!")
            print("Warning: No audio was recorded!")
            return None, None

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mic_path = None
        system_path = None

        print("\nSaved recordings:")

        # Save microphone audio
        if mic_data:
            mic_audio = np.concatenate(mic_data, axis=0)
            # Resample to target rate for Whisper if needed
            if self.mic_sample_rate != self.target_sample_rate:
                self.logger.debug(f"Resampling mic from {self.mic_sample_rate} to {self.target_sample_rate}")
                mic_audio = self._resample(mic_audio, self.mic_sample_rate, self.target_sample_rate)
            mic_path = self.output_dir / f"mic_{timestamp}.wav"
            wavfile.write(str(mic_path), self.target_sample_rate, mic_audio)
            duration = len(mic_audio) / self.target_sample_rate
            print(f"  Microphone: {mic_path.name} ({duration:.1f}s)")
            self.logger.info(f"Saved mic audio: {mic_path} ({duration:.1f}s)")

        # Save system audio
        if system_data:
            system_audio = np.concatenate(system_data, axis=0)
            # Resample to target rate for Whisper if needed
            if self.system_sample_rate != self.target_sample_rate:
                self.logger.debug(f"Resampling system from {self.system_sample_rate} to {self.target_sample_rate}")
                system_audio = self._resample(system_audio, self.system_sample_rate, self.target_sample_rate)
            system_path = self.output_dir / f"system_{timestamp}.wav"
            wavfile.write(str(system_path), self.target_sample_rate, system_audio)
            duration = len(system_audio) / self.target_sample_rate
            print(f"  System:     {system_path.name} ({duration:.1f}s)")
            self.logger.info(f"Saved system audio: {system_path} ({duration:.1f}s)")

        return mic_path, system_path

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate."""
        if orig_sr == target_sr:
            return audio

        # Calculate number of samples in output
        num_samples = int(len(audio) * target_sr / orig_sr)

        # Resample using scipy
        resampled = scipy_signal.resample(audio, num_samples)

        return resampled.astype(audio.dtype)

    def get_duration(self) -> float:
        """Get current recording duration in seconds."""
        if self.start_time and self.is_recording:
            return time.time() - self.start_time
        return 0.0


def test_audio_capture(device_index: int, duration: float = 3.0) -> bool:
    """Test audio capture from a specific device.

    Args:
        device_index: Device index to test
        duration: Test duration in seconds

    Returns:
        True if audio was captured successfully
    """
    logger = get_logger()
    logger.info(f"Testing device {device_index} for {duration}s...")

    audio_data = []

    def callback(indata, frames, time_info, status):
        if status:
            logger.warning(f"Status: {status}")
        audio_data.append(indata.copy())

    try:
        devices = sd.query_devices()
        dev = devices[device_index]
        # Use device's native sample rate
        device_sr = int(dev['default_samplerate'])
        print(f"\nTesting: [{device_index}] {dev['name']}")
        print(f"Sample rate: {device_sr} Hz")
        print(f"Recording for {duration} seconds...")

        with sd.InputStream(
            device=device_index,
            channels=1,
            samplerate=device_sr,
            blocksize=BLOCK_SIZE,
            callback=callback
        ):
            time.sleep(duration)

        if audio_data:
            audio = np.concatenate(audio_data)
            max_amplitude = np.max(np.abs(audio))
            rms = np.sqrt(np.mean(audio**2))

            print(f"\nResults:")
            print(f"  Samples captured: {len(audio)}")
            print(f"  Max amplitude: {max_amplitude:.4f}")
            print(f"  RMS level: {rms:.4f}")

            if max_amplitude > 0.001:
                print("  Status: Audio detected!")
                return True
            else:
                print("  Status: Very low/no audio (check if sound is playing)")
                return False
        else:
            print("  Status: No data captured!")
            return False

    except Exception as e:
        logger.exception(f"Test failed: {e}")
        print(f"\nError: {e}")
        return False


def check_system_audio_available() -> bool:
    """Check if system audio capture is available."""
    if IS_WINDOWS:
        # Check for WASAPI loopback
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()

        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                hostapi = hostapis[dev['hostapi']]['name']
                if 'WASAPI' in hostapi:
                    name_lower = dev['name'].lower()
                    if 'loopback' in name_lower or 'stereo mix' in name_lower:
                        return True
        return False

    elif IS_MAC:
        # Check for BlackHole
        devices = sd.query_devices()
        for dev in devices:
            if 'blackhole' in dev['name'].lower():
                return True
        return False

    return False
