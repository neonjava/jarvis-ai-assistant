#!/usr/bin/env python3
"""
JARVIS Push-to-Talk Hotkey Assistant (Ctrl + Super/WinKey)
1. Hold Ctrl + WinKey (Super) to record your voice.
2. Release either key to stop recording.
3. Faster-Whisper transcribes your voice to text and prints it.
4. Executes system command / asks AI assistant.
5. Speaks reply aloud via Text-To-Speech.
"""

import asyncio
import os
import sys
import threading
import time
import numpy as np
from pynput import keyboard

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from utils.logging import setup_logging
from voice.pipeline import SpeechToText, TextToSpeech, MicRecorder
from ai.engine import ai_engine
from ai.interpreter import CommandInterpreter
from system.controller import system


class HotkeyVoiceAssistant:
    def __init__(self):
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.mic = MicRecorder()
        self.interpreter = CommandInterpreter(ai_engine, system)

        self.ctrl_pressed = False
        self.alt_pressed = False
        self.is_recording = False
        self.recording_chunks = []
        self.loop = None
        self._stream = None

    async def initialize(self):
        setup_logging()
        print("\n" + "=" * 60)
        print(" 🎙️  JARVIS HOTKEY VOICE ASSISTANT (Ctrl + Alt)  🎙️")
        print("=" * 60)

        print("\n[1/3] Loading Speech-to-Text model (Faster-Whisper)...")
        await self.stt.initialize()

        print("[2/3] Loading Text-to-Speech engine...")
        await self.tts.initialize()

        print("[3/3] Initializing AI Engine...")
        await self.ai_engine_init()

        await self.tts.speak("JARVIS hotkey ready. Hold Ctrl and Alt to speak.")

        print("\n" + "─" * 60)
        print("💡 HOW TO USE:")
        print("  1. Press & HOLD [Ctrl] + [Alt].")
        print("  2. Speak your command into the microphone while holding keys.")
        print("  3. RELEASE the keys when done speaking.")
        print("  4. JARVIS will print your speech and reply aloud!")
        print("─" * 60 + "\n")

    async def ai_engine_init(self):
        await ai_engine.initialize()

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        self.recording_chunks = []
        print("\n🔴 [HOTKEY DETECTED] RECORDING VOICE... Speak now!")

        try:
            import sounddevice as sd

            def audio_cb(indata, frames, time_info, status):
                if self.is_recording:
                    self.recording_chunks.append(indata.copy())

            self._stream = sd.InputStream(
                samplerate=settings.AUDIO_SAMPLE_RATE,
                channels=settings.AUDIO_CHANNELS,
                dtype="int16",
                callback=audio_cb,
                blocksize=1024,
                device=settings.MIC_INDEX,
            )
            self._stream.start()
        except Exception as e:
            print(f"❌ Microphone record start error: {e}")

    def stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        print("⏹️  [KEYS RELEASED] STOPPED RECORDING. Processing audio...")

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self.recording_chunks:
            audio_np = np.concatenate(self.recording_chunks, axis=0)
            audio_bytes = audio_np.tobytes()
            # Dispatch async processing to loop
            if self.loop:
                asyncio.run_coroutine_threadsafe(self.process_audio(audio_bytes), self.loop)

    async def process_audio(self, audio_bytes: bytes):
        if len(audio_bytes) < 3200:
            print("⚠️ Audio too short. Please hold keys and speak clearly.")
            return

        print("⏳ Transcribing speech to text...")
        transcribed_text = await self.stt.transcribe(audio_bytes)

        if not transcribed_text:
            print("⚠️ Could not transcribe audio. Speak louder or hold keys while talking.")
            return

        print(f"\n🗣️ YOU SAID: \"{transcribed_text}\"")

        print("🤖 Processing command with JARVIS...")
        parsed_cmd = await self.interpreter.parse(transcribed_text)

        if parsed_cmd.requires_confirmation:
            reply = f"Confirmation required: {parsed_cmd.danger_message}"
        else:
            reply, _ = await self.interpreter.execute(parsed_cmd)

        print(f"⚡ JARVIS REPLY: \"{reply}\"\n")
        await self.tts.speak(reply)

    def on_press(self, key):
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = True
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            self.alt_pressed = True

        if self.ctrl_pressed and self.alt_pressed and not self.is_recording:
            self.start_recording()

    def on_release(self, key):
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = False
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            self.alt_pressed = False

        if not (self.ctrl_pressed and self.alt_pressed) and self.is_recording:
            self.stop_recording()

    def start_keyboard_listener(self):
        listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        listener.daemon = True
        listener.start()
        return listener


async def main():
    assistant = HotkeyVoiceAssistant()
    assistant.loop = asyncio.get_running_loop()
    await assistant.initialize()
    assistant.start_keyboard_listener()

    print("🟢 Hotkey Voice Assistant is active in background! Press Ctrl+C in terminal to stop.")
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting JARVIS Hotkey Voice Assistant.")
