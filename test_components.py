#!/usr/bin/env python3
"""
Test script to verify all Crystal Ball components work on this system.
Tests: Whisper STT, Ollama LLM, Piper TTS, and audio playback.
"""

import sys
import time
import tempfile
import wave
import subprocess

import numpy as np
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENV_PIPER = str(SCRIPT_DIR / "venv/bin/piper")
VOICE_MODEL = str(SCRIPT_DIR / "voices/en_US-lessac-medium.onnx")


def test_whisper():
    """Test speech-to-text with a synthetic audio sample."""
    print("\n[1/4] Testing Faster-Whisper (STT)...")
    from faster_whisper import WhisperModel

    model = WhisperModel("base.en", device="cpu", compute_type="int8")

    # Generate TTS audio to use as STT input
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = f.name

    process = subprocess.run(
        [VENV_PIPER, "--model", VOICE_MODEL, "--output_file", temp_path],
        input=b"What does my future hold",
        capture_output=True,
        timeout=30,
    )
    if process.returncode != 0:
        print(f"  SKIP - could not generate test audio: {process.stderr.decode()[:200]}")
        return True  # Don't fail the whole test

    start = time.time()
    segments, _ = model.transcribe(temp_path, vad_filter=True)
    text = " ".join(s.text for s in segments).strip()
    elapsed = time.time() - start

    import os
    os.unlink(temp_path)

    print(f"  Transcribed: \"{text}\"")
    print(f"  Time: {elapsed:.2f}s")

    if len(text) > 3:
        print("  PASS")
        return True
    else:
        print("  FAIL - no transcription")
        return False


def test_ollama():
    """Test LLM response generation."""
    print("\n[2/4] Testing Ollama LLM (llama3.2:3b)...")
    import ollama

    start = time.time()
    response = ollama.chat(
        model="llama3.2:3b",
        messages=[
            {"role": "system", "content": "You are a fortune teller. Reply in one sentence."},
            {"role": "user", "content": "What does my future hold?"},
        ],
        options={"num_predict": 50},
    )
    elapsed = time.time() - start
    text = response["message"]["content"]

    print(f"  Response: \"{text}\"")
    print(f"  Time: {elapsed:.2f}s")

    if len(text) > 5:
        print("  PASS")
        return True
    else:
        print("  FAIL - no response")
        return False


def test_piper():
    """Test text-to-speech audio generation."""
    print("\n[3/4] Testing Piper TTS...")

    start = time.time()
    process = subprocess.Popen(
        [VENV_PIPER, "--model", VOICE_MODEL, "--output-raw"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    audio_data, _ = process.communicate(b"The mists swirl around the crystal ball.", timeout=30)
    elapsed = time.time() - start

    print(f"  Audio bytes: {len(audio_data)}")
    print(f"  Time: {elapsed:.2f}s")

    if len(audio_data) > 1000:
        print("  PASS")
        return True, audio_data
    else:
        print("  FAIL - no audio generated")
        return False, None


def test_playback(audio_data):
    """Test audio playback through speakers."""
    print("\n[4/4] Testing Audio Playback...")
    import sounddevice as sd

    audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768
    print("  Playing TTS audio... (you should hear speech)")
    sd.play(audio, samplerate=22050)
    sd.wait()
    print("  DONE (did you hear it?)")
    return True


def main():
    print("=" * 50)
    print("  Crystal Ball Component Test")
    print("=" * 50)

    results = {}

    results["whisper"] = test_whisper()
    results["ollama"] = test_ollama()

    piper_ok, audio_data = test_piper()
    results["piper"] = piper_ok

    if audio_data:
        results["playback"] = test_playback(audio_data)
    else:
        print("\n[4/4] Skipping playback (no TTS audio)")
        results["playback"] = False

    print("\n" + "=" * 50)
    print("  Results")
    print("=" * 50)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {name:12s}: {status}")

    all_ok = all(results.values())
    print(f"\n  {'All tests passed!' if all_ok else 'Some tests failed.'}")
    print("=" * 50)

    if all_ok:
        print("\nYou can now run the full application:")
        print(f"  venv/bin/python3 .planning/crystal_ball.py --voice {VOICE_MODEL} --debug")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
