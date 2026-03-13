#!/usr/bin/env python3
"""
Parakeet V3 Alternative for Speech Recognition

NVIDIA's Parakeet V3 is an excellent alternative to Whisper:
- 600M parameters
- Excellent accuracy (rivals Whisper Large)
- Very fast on GPU (~60 minutes of audio in 1 second)
- ~5x real-time on CPU
- Automatic language detection (25 European languages)

This file shows how to use Parakeet instead of Faster-Whisper.

Setup is more complex than Faster-Whisper because it uses NVIDIA's NeMo toolkit.
"""

import os
import sys
import tempfile
import wave
import numpy as np


# =============================================================================
# Installation Instructions
# =============================================================================

INSTALL_INSTRUCTIONS = """
Parakeet V3 Installation
========================

1. Create a conda environment (recommended):
   conda create -n parakeet python=3.11 -y
   conda activate parakeet

2. Install PyTorch with CUDA support:
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

3. Install NeMo toolkit:
   pip install nemo_toolkit['asr']

4. Test installation:
   python -c "import nemo.collections.asr as nemo_asr; print('NeMo ready!')"

Note: NeMo is a heavy framework. For simpler setups, stick with Faster-Whisper.
Parakeet shines when you need to process large amounts of audio quickly.
"""


# =============================================================================
# Parakeet Speech Recognizer
# =============================================================================

class ParakeetRecognizer:
    """
    Speech recognition using NVIDIA Parakeet V3.
    
    This is more complex to set up than Faster-Whisper but offers
    excellent performance, especially on GPU.
    """
    
    def __init__(self, model_name: str = "nvidia/parakeet-tdt-0.6b-v3"):
        try:
            import nemo.collections.asr as nemo_asr
            import torch
        except ImportError:
            print("NeMo toolkit not installed.")
            print(INSTALL_INSTRUCTIONS)
            sys.exit(1)
        
        self.torch = torch
        
        # Check for GPU
        if torch.cuda.is_available():
            print(f"Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("GPU not available, using CPU (will be slower)")
        
        print(f"Loading Parakeet model ({model_name})...")
        self.model = nemo_asr.models.ASRModel.from_pretrained(model_name)
        print("Parakeet ready!")
    
    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe audio using Parakeet.
        
        Args:
            audio: numpy array of audio samples (float32)
            sample_rate: audio sample rate (should be 16000)
        
        Returns:
            Transcribed text
        """
        # Save to temp file (NeMo expects file input)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            
            with wave.open(temp_path, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes((audio * 32767).astype(np.int16).tobytes())
            
            try:
                # Transcribe
                transcriptions = self.model.transcribe([temp_path])
                
                # Handle different return formats
                if isinstance(transcriptions, list):
                    if len(transcriptions) > 0:
                        result = transcriptions[0]
                        # Some versions return dict with 'text' key
                        if isinstance(result, dict):
                            return result.get('text', str(result))
                        return str(result)
                    return ""
                return str(transcriptions)
                
            finally:
                os.unlink(temp_path)


# =============================================================================
# Simplified Wrapper (matches Faster-Whisper interface)
# =============================================================================

class SpeechRecognizer:
    """
    Drop-in replacement for the Faster-Whisper based recognizer.
    Use this class in crystal_ball.py instead of the default.
    """
    
    def __init__(self, model_size: str = "nvidia/parakeet-tdt-0.6b-v3", device: str = "auto"):
        self.recognizer = ParakeetRecognizer(model_name=model_size)
        self.sample_rate = 16000
    
    def record_until_silence(self) -> np.ndarray | None:
        """
        Record audio until silence is detected.
        (Same implementation as in crystal_ball.py)
        """
        import sounddevice as sd
        
        SILENCE_THRESHOLD = 0.01
        SILENCE_DURATION = 1.5
        MAX_DURATION = 15
        
        frames = []
        silent_chunks = 0
        chunk_duration = 0.1
        chunk_samples = int(self.sample_rate * chunk_duration)
        silence_chunks_needed = int(SILENCE_DURATION / chunk_duration)
        max_chunks = int(MAX_DURATION / chunk_duration)
        
        recording = True
        speech_started = False
        
        def callback(indata, frame_count, time_info, status):
            nonlocal silent_chunks, speech_started, recording
            
            volume = np.abs(indata).mean()
            frames.append(indata.copy())
            
            if volume > SILENCE_THRESHOLD:
                speech_started = True
                silent_chunks = 0
            elif speech_started:
                silent_chunks += 1
                if silent_chunks >= silence_chunks_needed:
                    recording = False
            
            if len(frames) >= max_chunks:
                recording = False
        
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=callback,
            blocksize=chunk_samples
        ):
            while recording:
                sd.sleep(100)
        
        if not frames:
            return None
        
        audio = np.concatenate(frames, axis=0)
        return audio.flatten()
    
    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio using Parakeet."""
        return self.recognizer.transcribe(audio, self.sample_rate)


# =============================================================================
# Comparison Notes
# =============================================================================

COMPARISON = """
Faster-Whisper vs Parakeet V3 Comparison
========================================

                    Faster-Whisper          Parakeet V3
-----------------------------------------------------------------
Installation        pip install             NeMo toolkit (complex)
Model Size          base: 142MB             ~600MB
                    small: 466MB
                    
CPU Speed           ~10x real-time          ~5x real-time
GPU Speed           ~50x real-time          ~60 minutes in 1 second!

Accuracy            Excellent               Excellent (slightly better)
Languages           100+                    25 European
VAD Built-in        Yes (Silero)            No (add separately)

Best For:
- Quick setup, simple projects: Faster-Whisper
- High-volume processing, GPU available: Parakeet
- This crystal ball project: Faster-Whisper (simpler)
"""


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("Parakeet V3 Alternative Speech Recognition")
    print("=" * 50)
    print(INSTALL_INSTRUCTIONS)
    print(COMPARISON)
    
    # Try to test if NeMo is available
    try:
        import nemo.collections.asr as nemo_asr
        print("\n✅ NeMo is installed! You can use Parakeet.")
        print("\nTo use in crystal_ball.py, change the import:")
        print("  from parakeet_alternative import SpeechRecognizer")
    except ImportError:
        print("\n⚠️  NeMo not installed. Using Faster-Whisper is recommended")
        print("   for this project due to simpler setup.")
