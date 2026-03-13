# Research Notes - Crystal Ball Project

This document contains background research, links, and technical notes gathered
during project planning.

---

## Speech-to-Text Options

### Faster-Whisper (Recommended)

**Repository:** https://github.com/SYSTRAN/faster-whisper

Optimized implementation of OpenAI's Whisper model using CTranslate2.

**Key Features:**
- 4x faster than original Whisper with same accuracy
- Built-in Silero VAD support
- Multiple model sizes (tiny, base, small, medium, large)
- Runs well on CPU with int8 quantization

**Model Sizes:**
| Model | Size | Relative Speed |
|-------|------|----------------|
| tiny.en | 39MB | Fastest |
| base.en | 142MB | Fast |
| small.en | 466MB | Moderate |
| medium.en | 1.5GB | Slow |
| large-v3 | 3GB | Slowest |

For interactive use, `base.en` offers good balance of speed and accuracy.


### NVIDIA Parakeet V3

**Hugging Face:** https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
**Technical Blog:** https://developer.nvidia.com/blog/pushing-the-boundaries-of-speech-recognition-with-nemo-parakeet-asr-models/

600M parameter ASR model from NVIDIA, currently #1 on Hugging Face ASR leaderboard.

**Key Features:**
- Excellent accuracy (rivals/beats Whisper Large)
- 25 European language support with auto-detection
- ~60 minutes of audio in 1 second on GPU
- ~5x real-time on CPU

**Drawbacks:**
- Requires NeMo toolkit (heavy dependency)
- More complex setup than Faster-Whisper
- Overkill for short interactive utterances


### Handy Project

**Repository:** https://github.com/cjpais/handy
**Website:** https://handy.computer

Open source speech-to-text desktop app using similar stack. Good reference for:
- Silero VAD integration
- Audio handling patterns
- Cross-platform considerations

---

## Voice Activity Detection

### Silero VAD

**Repository:** https://github.com/snakers4/silero-vad
**PyPI:** https://pypi.org/project/silero-vad/

**Why VAD is Important:**
Whisper hallucinates phrases like "Thank you for listening" when processing silence.
VAD filters out non-speech segments before transcription.

**Key Specs:**
- ~2MB model size
- <1ms per 30ms audio chunk on CPU
- Trained on 6000+ languages
- MIT licensed

**Usage:**
```python
# Standalone
import torch
model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad')
speech_timestamps = utils[0](audio, model)

# Built into faster-whisper
segments, _ = model.transcribe(audio_file, vad_filter=True)
```

---

## Local LLM Options

### Ollama

**Website:** https://ollama.com/
**GitHub:** https://github.com/ollama/ollama

Easy local LLM hosting. Recommended for this project.

**Installation:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral
```

**Models for 16GB RAM:**

| Model | Size | Quality | Use Case |
|-------|------|---------|----------|
| llama3.2:3b | ~2GB | Good | Fast responses |
| mistral | ~4GB | Better | Recommended |
| phi3 | ~2GB | Good | Alternative |
| llama3.1:8b | ~5GB | Best | If speed allows |


### llama.cpp

**Repository:** https://github.com/ggerganov/llama.cpp

Lower-level alternative to Ollama. More control, more complex setup.

---

## Text-to-Speech Options

### Piper TTS (Recommended)

**Repository:** https://github.com/rhasspy/piper
**Voice Samples:** https://rhasspy.github.io/piper-samples/

Fast, high-quality offline TTS.

**Installation:**
```bash
pip install piper-tts
```

**Usage:**
```bash
echo "Hello world" | piper --model en_US-lessac-medium --output-raw | aplay -r 22050 -f S16_LE
```

**Voice Recommendations for Fortune Teller:**
- `en_US-lessac-medium` - Clear, neutral
- `en_GB-alba-medium` - British accent
- Custom: Could potentially fine-tune for "mystical" voice


### Coqui TTS

**Repository:** https://github.com/coqui-ai/TTS

More voice options but heavier. Good if you want voice cloning.


### Edge TTS

**PyPI:** https://pypi.org/project/edge-tts/

Microsoft's free TTS API. Requires internet but no API key.
Good fallback if Piper voices don't sound right.

```bash
pip install edge-tts
edge-tts --text "Hello" --write-media hello.mp3
```

---

## Hardware Considerations

### Mini PC Recommendations

For Ryzen 5 + 16GB RAM:
- Faster-Whisper base model: ~2 seconds for 10s audio
- Mistral 7B via Ollama: ~1-2 seconds for short response
- Piper TTS: <1 second

**Total expected latency:** 2-4 seconds (acceptable for theatrical pause)


### Audio Hardware

**Microphone:**
- USB condenser mic for clear input
- Consider directional mic to reduce background noise
- Test sensitivity with `test_microphone.py`

**Speakers:**
- Any powered speakers work
- Consider placement for theatrical effect
- Test volume levels in actual venue


### LED Options

**WS2812B (NeoPixel) strips:**
- Easy to control
- Many effects possible
- Can be driven by Arduino, Pico, or ESP8266

**Controllers:**
- Arduino Nano: Simple, reliable
- Raspberry Pi Pico: Cheap, powerful
- ESP8266 with WLED: WiFi control, many built-in effects

---

## Alternative Approaches Considered

### SillyTavern

**Website:** https://sillytavernai.com/

Chat-based roleplay interface for LLMs. Considered but rejected because:
- UI-centric design (we want voice-first)
- Overkill for single-character use case
- Would require significant adaptation

### Rhasspy

**Website:** https://rhasspy.readthedocs.io/

Offline voice assistant toolkit. Considered but:
- Designed for command/intent patterns
- More complex than needed for freeform fortune telling
- Good for future projects though!

### Home Assistant + Wyoming

Voice assistant protocol from Home Assistant. Interesting for:
- Integration with home automation
- LED control via automations
- But adds unnecessary complexity for standalone prop

---

## Performance Benchmarks (Expected)

Based on Ryzen 5 + 16GB RAM:

| Component | Expected Time |
|-----------|---------------|
| VAD processing | <10ms |
| Whisper base.en (10s audio) | 1-2s |
| Ollama Mistral (short response) | 1-2s |
| Piper TTS (2-3 sentences) | <1s |
| **Total round-trip** | **2-4s** |

This is acceptable for the theatrical "communing with spirits" pause.

---

## Links Summary

**Speech Recognition:**
- https://github.com/SYSTRAN/faster-whisper
- https://github.com/snakers4/silero-vad
- https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3

**Local LLM:**
- https://ollama.com/
- https://github.com/ggerganov/llama.cpp

**Text-to-Speech:**
- https://github.com/rhasspy/piper
- https://rhasspy.github.io/piper-samples/

**Reference Projects:**
- https://github.com/cjpais/handy

**LED Control:**
- https://kno.wled.ge/ (WLED firmware)
- https://learn.adafruit.com/adafruit-neopixel-uberguide

---

*Last updated: January 2026*
