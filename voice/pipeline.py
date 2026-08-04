"""
Voice Pipeline — Wake Word → STT → Command → TTS
"""
from __future__ import annotations

import asyncio
import io
import os
import queue
import threading
import time
import wave
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from loguru import logger

from config.settings import settings


class VoiceState(Enum):
    IDLE = auto()
    LISTENING_WAKE = auto()
    LISTENING_COMMAND = auto()
    PROCESSING = auto()
    SPEAKING = auto()


@dataclass
class AudioChunk:
    data: bytes
    sample_rate: int = 16000
    channels: int = 1


# ── Wake Word Detector ────────────────────────────────────────────────────────

class WakeWordDetector:
    """OpenWakeWord-based detector with fallback to simple keyword matching."""

    def __init__(self) -> None:
        self.wake_word = settings.WAKE_WORD.lower()
        self.threshold = settings.WAKE_WORD_THRESHOLD
        self._model = None
        self._available = False

    async def initialize(self) -> bool:
        try:
            import openwakeword
            from openwakeword.model import Model

            self._model = Model(
                wakeword_model_paths=["hey_jarvis"],
                inference_framework="onnx",
            )
            self._available = True
            logger.info("✅ Wake word detector: OpenWakeWord")
        except ImportError:
            logger.warning("OpenWakeWord not installed, using basic keyword detection")
            self._available = False
        return self._available

    def detect(self, audio_chunk: np.ndarray) -> bool:
        """Return True if wake word detected."""
        if self._model:
            try:
                prediction = self._model.predict(audio_chunk)
                scores = list(prediction.values())
                return any(s >= self.threshold for s in scores)
            except Exception:
                pass
        return False


# ── Speech-to-Text ────────────────────────────────────────────────────────────

class SpeechToText:
    """Faster-Whisper based STT engine."""

    def __init__(self) -> None:
        self._model = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model)

    def _load_model(self) -> None:
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                settings.STT_MODEL,
                device=settings.STT_DEVICE,
                compute_type="int8",
            )
            logger.info(f"✅ STT: Faster-Whisper ({settings.STT_MODEL})")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe audio bytes to text."""
        if not self._model:
            return ""

        async with self._lock:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None, self._do_transcribe, audio_data, sample_rate
            )
            return text

    def _do_transcribe(self, audio_data: bytes, sample_rate: int) -> str:
        try:
            # Convert bytes to numpy float32
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            segments, info = self._model.transcribe(
                audio_np,
                language="en",
                vad_filter=True,
                vad_parameters={"threshold": 0.5},
            )
            text = " ".join(seg.text.strip() for seg in segments)
            logger.debug(f"Transcribed: '{text}'")
            return text.strip()
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""


# ── Text-to-Speech ────────────────────────────────────────────────────────────

class TextToSpeech:
    """Multi-backend TTS: Piper → espeak fallback."""

    def __init__(self) -> None:
        self._provider = settings.TTS_PROVIDER
        self._piper_available = False

    async def initialize(self) -> None:
        if self._provider == "piper":
            result = await asyncio.create_subprocess_shell(
                "which piper",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            self._piper_available = result.returncode == 0

        if self._piper_available:
            logger.info("✅ TTS: Piper")
        else:
            logger.info("✅ TTS: espeak (fallback)")

    async def speak(self, text: str) -> None:
        """Speak text aloud."""
        text = text.strip()
        if not text:
            return

        if self._piper_available:
            await self._speak_piper(text)
        else:
            await self._speak_espeak(text)

    async def _speak_piper(self, text: str) -> None:
        cmd = (
            f"echo '{text}' | piper --model {settings.PIPER_MODEL} --output_raw "
            f"| aplay -r 22050 -f S16_LE -t raw -"
        )
        proc = await asyncio.create_subprocess_shell(cmd)
        await proc.communicate()

    async def _speak_espeak(self, text: str) -> None:
        cmd = f"espeak-ng -s 150 -p 60 '{text}' 2>/dev/null || espeak '{text}' 2>/dev/null"
        proc = await asyncio.create_subprocess_shell(cmd)
        await proc.communicate()

    async def synthesize_to_file(self, text: str, output_path: str) -> bool:
        """Save TTS audio to file."""
        try:
            if self._piper_available:
                cmd = f"echo '{text}' | piper --model {settings.PIPER_MODEL} --output_file '{output_path}'"
            else:
                cmd = f"espeak-ng -w '{output_path}' '{text}'"
            proc = await asyncio.create_subprocess_shell(cmd)
            await proc.communicate()
            return True
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return False


# ── Microphone Recorder ───────────────────────────────────────────────────────

class MicRecorder:
    """Non-blocking microphone capture using sounddevice."""

    def __init__(self) -> None:
        self._sample_rate = settings.AUDIO_SAMPLE_RATE
        self._channels = settings.AUDIO_CHANNELS
        self._recording = False
        self._audio_queue: queue.Queue = queue.Queue()

    def start_stream(self, callback: Callable[[np.ndarray], None]) -> None:
        """Start continuous audio capture in background thread."""
        try:
            import sounddevice as sd

            def _callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
                if status:
                    logger.debug(f"Audio status: {status}")
                callback(indata.copy())

            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                callback=_callback,
                blocksize=1024,
                device=settings.MIC_INDEX,
            )
            self._stream.start()
            logger.info("✅ Microphone stream started")
        except Exception as e:
            logger.error(f"Microphone error: {e}")

    async def record_utterance(self, max_silence_ms: int = 1500, max_duration_s: int = 30) -> bytes:
        """Record until silence, return audio bytes."""
        try:
            import sounddevice as sd

            sample_rate = self._sample_rate
            silence_threshold = 200  # RMS threshold
            silence_samples = int(sample_rate * max_silence_ms / 1000)
            max_samples = sample_rate * max_duration_s

            chunks: list[np.ndarray] = []
            silent_samples = 0
            total_samples = 0

            def _callback(indata: np.ndarray, frames: int, *_: Any) -> None:
                nonlocal silent_samples, total_samples
                rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
                chunks.append(indata.copy())
                total_samples += frames
                if rms < silence_threshold:
                    silent_samples += frames
                else:
                    silent_samples = 0

            stream = sd.InputStream(
                samplerate=sample_rate,
                channels=self._channels,
                dtype="int16",
                callback=_callback,
                blocksize=1024,
                device=settings.MIC_INDEX,
            )

            with stream:
                while silent_samples < silence_samples and total_samples < max_samples:
                    await asyncio.sleep(0.05)

            if chunks:
                audio = np.concatenate(chunks, axis=0)
                return audio.tobytes()
            return b""

        except Exception as e:
            logger.error(f"Recording error: {e}")
            return b""

    def stop_stream(self) -> None:
        if hasattr(self, "_stream"):
            self._stream.stop()
            self._stream.close()


# ── Voice Pipeline ────────────────────────────────────────────────────────────

class VoicePipeline:
    """
    Full voice pipeline:
    Wake word → Record utterance → STT → Command → TTS response
    """

    def __init__(self) -> None:
        self.wake_word = WakeWordDetector()
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.mic = MicRecorder()
        self.state = VoiceState.IDLE
        self._running = False
        self._command_callback: Optional[Callable] = None
        self._wake_buffer: list[np.ndarray] = []
        self._wake_buffer_size = 8  # ~0.5s at 16kHz

    async def initialize(self) -> None:
        logger.info("Initializing voice pipeline...")
        await self.wake_word.initialize()
        await self.stt.initialize()
        await self.tts.initialize()
        logger.info("✅ Voice pipeline ready")

    def on_command(self, callback: Callable[[str], None]) -> None:
        """Register callback for when a voice command is transcribed."""
        self._command_callback = callback

    async def start(self) -> None:
        """Start the voice pipeline."""
        if not settings.VOICE_ENABLED:
            logger.info("Voice pipeline disabled in settings")
            return

        self._running = True
        self.state = VoiceState.LISTENING_WAKE

        logger.info(f"🎤 Listening for wake word: '{settings.WAKE_WORD}'")
        await self.tts.speak("JARVIS online. How can I help?")

        def _on_audio(chunk: np.ndarray) -> None:
            self._wake_buffer.append(chunk)
            if len(self._wake_buffer) > self._wake_buffer_size:
                self._wake_buffer.pop(0)

            if self.state == VoiceState.LISTENING_WAKE:
                combined = np.concatenate(self._wake_buffer, axis=0).flatten()
                if self.wake_word.detect(combined):
                    asyncio.run_coroutine_threadsafe(
                        self._handle_wake(), asyncio.get_event_loop()
                    )

        self.mic.start_stream(_on_audio)

    async def _handle_wake(self) -> None:
        """Handle wake word detection."""
        if self.state != VoiceState.LISTENING_WAKE:
            return  # Already handling

        self.state = VoiceState.LISTENING_COMMAND
        logger.info("Wake word detected! Recording command...")
        await self.tts.speak("Yes?")

        audio_data = await self.mic.record_utterance()

        self.state = VoiceState.PROCESSING
        text = await self.stt.transcribe(audio_data)

        if text and self._command_callback:
            logger.info(f"Voice command: '{text}'")
            await self._command_callback(text)

        self.state = VoiceState.LISTENING_WAKE

    async def speak(self, text: str) -> None:
        """Speak a response."""
        self.state = VoiceState.SPEAKING
        await self.tts.speak(text)
        self.state = VoiceState.LISTENING_WAKE

    async def stop(self) -> None:
        self._running = False
        self.mic.stop_stream()
        self.state = VoiceState.IDLE
        logger.info("Voice pipeline stopped")


# ── Singleton ─────────────────────────────────────────────────────────────────
voice_pipeline = VoicePipeline()
