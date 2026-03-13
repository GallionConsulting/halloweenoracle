# Halloween Crystal Ball Project

## Project
- "Madam Zelda's Crystal Ball" - AI Halloween fortune teller
- Planning docs in `.planning/` directory
- Main app: `.planning/crystal_ball.py`

## System
- Linux Mint, AMD Ryzen 7 5700U, 12GB RAM, no NVIDIA GPU (CPU-only inference)
- Python 3.12.3, venv at `venv/`
- Audio devices: device 4 (ALC897 Analog) for input, device 9 (default/pipewire) for default

## Installed Components
- **STT**: faster-whisper with base.en model, Silero VAD built-in. Transcription ~0.87s for short audio.
- **LLM**: Ollama 0.17.7 with `mistral` (~5.8s) and `llama3.2:3b` (~11.7s on first run, should be faster cached)
- **TTS**: piper-tts with `en_US-lessac-medium` voice model in `voices/` dir. ~1.75s for a sentence.
- **Audio**: sounddevice + numpy

## Key Paths
- Voice model: `voices/en_US-lessac-medium.onnx`
- Test script: `test_components.py`
- Piper binary: `venv/bin/piper`
- Run command: `venv/bin/python3 .planning/crystal_ball.py --voice voices/en_US-lessac-medium.onnx --debug`

## Notes
- piper-tts needed `pathvalidate` installed separately (missing dependency)
- The `.planning/crystal_ball.py` TTS class calls `piper` by name - needs path update to `venv/bin/piper` and voice model path for this setup
- llama3.2:3b was slower than mistral on first test (cold start) - mistral is recommended per docs
