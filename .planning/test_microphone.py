#!/usr/bin/env python3
"""
Test script to verify microphone input is working correctly.

Run this before the main crystal_ball.py to ensure audio capture works.
"""

import numpy as np
import sounddevice as sd
import sys

SAMPLE_RATE = 16000
DURATION = 5  # seconds


def list_devices():
    """List all audio devices."""
    print("\n=== Available Audio Devices ===\n")
    print(sd.query_devices())
    print()


def test_recording(device=None):
    """Test recording from microphone."""
    print(f"\n=== Recording Test ({DURATION} seconds) ===\n")
    
    if device is not None:
        print(f"Using device: {device}")
    else:
        print(f"Using default input device")
    
    print("Speak now...")
    
    try:
        recording = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='float32',
            device=device
        )
        sd.wait()
        
        # Analyze recording
        volume = np.abs(recording).mean()
        peak = np.abs(recording).max()
        
        print(f"\nRecording complete!")
        print(f"  Average volume: {volume:.6f}")
        print(f"  Peak volume: {peak:.6f}")
        print(f"  Samples: {len(recording)}")
        
        # Recommendations
        print("\n=== Recommendations ===\n")
        
        if peak < 0.01:
            print("⚠️  Very low volume detected!")
            print("   - Check microphone connection")
            print("   - Try increasing system input volume")
            print("   - Speak closer to the microphone")
        elif peak < 0.05:
            print("⚠️  Low volume detected")
            print("   - Consider lowering SILENCE_THRESHOLD in crystal_ball.py")
            print(f"   - Suggested: SILENCE_THRESHOLD = {volume * 0.5:.4f}")
        else:
            print("✅ Volume levels look good!")
            print(f"   - Suggested SILENCE_THRESHOLD: {volume * 0.3:.4f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Recording failed: {e}")
        return False


def test_playback():
    """Test audio playback."""
    print("\n=== Playback Test ===\n")
    print("Playing test tone...")
    
    try:
        # Generate a simple tone
        duration = 1.0
        frequency = 440  # A4
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
        tone = np.sin(frequency * t * 2 * np.pi) * 0.3
        
        sd.play(tone.astype(np.float32), samplerate=SAMPLE_RATE)
        sd.wait()
        
        print("✅ Playback complete! Did you hear the tone?")
        return True
        
    except Exception as e:
        print(f"❌ Playback failed: {e}")
        return False


def main():
    print("=" * 50)
    print("    Audio System Test for Crystal Ball")
    print("=" * 50)
    
    # List devices
    list_devices()
    
    # Get device selection
    print("Enter device number to test (or press Enter for default): ", end="")
    device_input = input().strip()
    device = int(device_input) if device_input else None
    
    # Test recording
    if not test_recording(device):
        sys.exit(1)
    
    # Test playback
    print("\nTest playback? [Y/n]: ", end="")
    if input().strip().lower() != 'n':
        test_playback()
    
    print("\n" + "=" * 50)
    print("    Tests Complete!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
