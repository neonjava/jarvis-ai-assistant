#!/usr/bin/env python3
"""
JARVIS Direct Voice Assistant
1. Listens directly to your voice (press Enter to speak or speak freely).
2. Transcribes spoken speech to text using Faster-Whisper.
3. Prints transcribed text to console.
4. Executes system command / asks AI assistant.
5. Speaks the response aloud using Text-to-Speech (espeak/piper).
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


async def voice_dictation_loop():
    setup_logging()
    print("\n" + "=" * 60)
    print("  🎙️  JARVIS VOICE-TO-TEXT & SPEECH ASSISTANT  🎙️")
    print("=" * 60)

    stt = SpeechToText()
    tts = TextToSpeech()
    mic = MicRecorder()
    interpreter = CommandInterpreter(ai_engine, system)

    print("\n[1/3] Loading Speech-to-Text model (Faster-Whisper)...")
    await stt.initialize()

    print("[2/3] Loading Text-to-Speech engine...")
    await tts.initialize()

    print("[3/3] Initializing AI Engine...")
    await ai_engine.initialize()

    await tts.speak("JARVIS voice system ready. Speak your command.")

    print("\n" + "─" * 60)
    print("💡 INSTRUCTIONS:")
    print("  1. Press ENTER to start recording your voice.")
    print("  2. Speak your command/question clearly.")
    print("  3. Stop speaking for 3.5 seconds.")
    print("  4. JARVIS will print your text and speak the answer!")
    print("─" * 60 + "\n")

    while True:
        try:
            input("👉 Press [ENTER] to speak (Ctrl+C to quit)... ")
            print("🔴 RECORDING... (Speak now, auto-stops on silence)")

            audio_bytes = await mic.record_utterance(max_silence_ms=3500, max_duration_s=25)

            if not audio_bytes or len(audio_bytes) < 3200:
                print("⚠️  No speech detected. Try again.")
                continue

            print("⏳ Transcribing audio to text...")
            transcribed_text = await stt.transcribe(audio_bytes)

            if not transcribed_text:
                print("⚠️  Could not transcribe speech. Please speak louder/clearer.")
                continue

            print(f"\n🗣️  YOU SAID: \"{transcribed_text}\"")

            print("🤖 Processing with JARVIS...")
            parsed_cmd = await interpreter.parse(transcribed_text)

            if parsed_cmd.requires_confirmation:
                reply = f"Warning: {parsed_cmd.danger_message}"
            else:
                reply, _ = await interpreter.execute(parsed_cmd)

            print(f"⚡ JARVIS REPLY: \"{reply}\"\n")

            await tts.speak(reply)

        except KeyboardInterrupt:
            print("\nShutting down JARVIS voice assistant.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(voice_dictation_loop())
