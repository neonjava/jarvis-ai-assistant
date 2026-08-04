#!/usr/bin/env python3
"""
JARVIS Automatic Continuous Voice Assistant (No hotkeys needed!)
1. Runs continuously in your terminal.
2. Listens for speech dynamically.
3. Automatically transcribes speech to text as soon as you stop talking (2s silence).
4. Prints text to console, executes system action or asks AI, and speaks response.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from utils.logging import setup_logging
from voice.pipeline import SpeechToText, TextToSpeech, MicRecorder
from ai.engine import ai_engine
from ai.interpreter import CommandInterpreter
from system.controller import system


async def continuous_voice_loop():
    setup_logging()
    print("\n" + "=" * 60)
    print("  🎙️  JARVIS AUTOMATIC CONTINUOUS VOICE ASSISTANT  🎙️")
    print("=" * 60)

    stt = SpeechToText()
    tts = TextToSpeech()
    mic = MicRecorder()
    interpreter = CommandInterpreter(ai_engine, system)

    print("\n[1/3] Loading Speech-to-Text engine (Faster-Whisper)...")
    await stt.initialize()

    print("[2/3] Loading Text-to-Speech engine...")
    await tts.initialize()

    print("[3/3] Initializing AI Engine...")
    await ai_engine.initialize()

    print("\n" + "─" * 60)
    print("🟢 AUTOMATIC LISTENING IS ACTIVE!")
    print("   Just speak anytime. JARVIS will automatically record,")
    print("   print your speech, and speak the reply back to you!")
    print("   (Press Ctrl+C to exit)")
    print("─" * 60 + "\n")

    await tts.speak("JARVIS automatic listening online. Speak anytime.")

    while True:
        try:
            print("🎤 Listening... (Speak now)")
            # Auto-record until 2 seconds of silence
            audio_bytes = await mic.record_utterance(max_silence_ms=2000, max_duration_s=20)

            if not audio_bytes or len(audio_bytes) < 4000:
                continue

            print("⏳ Transcribing speech...")
            text = await stt.transcribe(audio_bytes)

            if not text or len(text.strip()) < 2:
                continue

            print(f"\n🗣️  YOU SAID: \"{text}\"")

            print("🤖 Processing with JARVIS...")
            parsed_cmd = await interpreter.parse(text)

            if parsed_cmd.requires_confirmation:
                reply = f"Warning: {parsed_cmd.danger_message}"
            else:
                reply, _ = await interpreter.execute(parsed_cmd)

            print(f"⚡ JARVIS REPLY: \"{reply}\"\n")

            # Speak answer aloud
            await tts.speak(reply)
            await asyncio.sleep(0.5)

        except KeyboardInterrupt:
            print("\nStopping automatic voice assistant.")
            break
        except Exception as e:
            print(f"❌ Voice loop error: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(continuous_voice_loop())
