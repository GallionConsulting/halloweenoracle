# The Crystal Ball

An AI-powered Halloween fortune teller. Visitors approach a crystal ball, ask a question, and receive a spooky fortune. Choose between **Madam Zelda** (default) or **Baron Mordecai** as your fortune teller. Runs entirely offline on a mini PC.

**Stack:** Faster-Whisper (speech-to-text) + Ollama/Llama 3.2 (fortune generation) + Piper TTS (speech output)

## Quick Start

```bash
./run.sh
```

Pass any flags through to the main app:

```bash
./run.sh --persona mordecai          # Baron Mordecai (male, ominous)
./run.sh --model mistral             # Use Mistral 7B
./run.sh --length-scale 1.4          # Slower, more dramatic speech
```

## Installation

### 1. System Dependencies

```bash
sudo apt update
sudo apt install -y ffmpeg portaudio19-dev python3-pip
pip install piper-tts
```

### 2. Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
```

**Vulkan acceleration (AMD GPUs):** Add these to `/etc/systemd/system/ollama.service` under `[Service]`:

```ini
Environment="OLLAMA_VULKAN=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
```

Then `sudo systemctl daemon-reload && sudo systemctl restart ollama`.

### 3. Python Dependencies

```bash
pip install -r .planning/requirements.txt
```

### 4. Voice Models

Six Piper voices are included in `voices/`. Download more from the [Piper voices repository](https://huggingface.co/rhasspy/piper-voices/tree/main/en) (grab both `.onnx` and `.onnx.json` files). Preview voices at [Piper voice samples](https://rhasspy.github.io/piper-samples/).

| Voice | Description |
|-------|-------------|
| **en_GB-alba-medium** | British female, warm (default) |
| en_GB-jenny_dioco-medium | British female, expressive |
| en_GB-semaine-medium | British RP, 4 speakers: prudence (0), spike (1), **obadiah (2)**, poppy (3) |
| en_GB-northern_english_male-medium | Northern English male, deep and distinctive |
| en_GB-alan-medium | British male |
| en_US-lessac-medium | American, neutral |

### 5. Verify Setup

```bash
# Test all components at once
venv/bin/python3 test_components.py

# Or test individually:
ollama run llama3.2:3b "Say hello in a spooky voice"
echo "The spirits are listening" | piper --model voices/en_GB-alba-medium.onnx --length-scale 1.2 --output-raw | aplay -r 22050 -f S16_LE
python .planning/test_microphone.py
```

## Usage

```bash
./run.sh
```

The system announces itself, listens for a question, generates a fortune, speaks it, and loops. Say "goodbye" to exit.

### Personas

| Persona | Character | Voice | Style |
|---------|-----------|-------|-------|
| **zelda** (default) | Madam Zelda | en_GB-alba-medium | Playfully spooky, warm |
| **mordecai** | Baron Mordecai | en_GB-semaine-medium (obadiah) | Brooding, ominous, grave |

### Options

```
--persona PERSONA     Fortune teller persona: zelda, mordecai (default: zelda)
--model MODEL         Ollama model (default: llama3.2:3b)
--voice VOICE         Piper voice model path (overrides persona default)
--length-scale N      Speech speed, higher = slower (default: 1.2)
--sentence-silence N  Pause between sentences in seconds (default: 0.3)
--speaker ID          Speaker ID for multi-speaker voice models
--mic-device ID       Microphone device index
--list-devices        List audio devices and exit
--debug               Show timing and debug info
```

### Speech Tuning

| `--length-scale` | Effect |
|-------------------|--------|
| `0.75` | Fast (testing) |
| `1.0` | Normal |
| **`1.2`** | **Slightly slow (default)** |
| `1.4` | Dramatic |
| `1.6` | Maximum spookiness |

Combine options for full theatrical delivery:

```bash
./run.sh --length-scale 1.3 --sentence-silence 0.5
```

**Compare voices without running the full app:**

```bash
TEXT="The mists swirl... I see a journey in your future. Beware the stranger at the crossroads."
for voice in voices/*.onnx; do
  echo "--- $voice ---"
  echo "$TEXT" | piper --model "$voice" --length-scale 1.2 --output-raw | aplay -r 22050 -f S16_LE
done
```

### Selecting a Microphone

```bash
./run.sh --list-devices     # Find your mic's index
./run.sh --mic-device 3     # Use that index
```

You can also set the default input device system-wide via Sound Settings or `pavucontrol`.

## Customization

### Changing the Personality

Edit the `PERSONAS` dict in `.planning/crystal_ball.py`. Each persona defines its system prompt, voice, filler phrases, and greeting/farewell lines. Keep responses limited to 2-3 sentences, include example phrases, and specify what to avoid (breaking character, etc.).

### LED Effects

See `.planning/led_integration.py` for WLED (WiFi), Arduino/Pico (serial), and dummy controllers with a full integration example.

### Cloud LLM (Instead of Local)

See `.planning/cloud_api_example.py` for Claude and OpenAI API integration. Useful if you want higher quality responses and have internet access.

### LLM Model Options

| Model | RAM | Notes |
|-------|-----|-------|
| **llama3.2:3b** | ~2GB | Default, fast |
| mistral | ~4GB | Higher quality |
| phi3 | ~2GB | Alternative small model |
| llama3.1:8b | ~5GB | Best quality, slower |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Whisper hallucinating phrases on silence | VAD should be enabled (`vad_filter=True` in transcribe call) |
| Responses too slow | Enable Vulkan for Ollama; use `llama3.2:3b`; reduce `max_tokens` |
| Voice too fast/slow | Adjust `--length-scale` (higher = slower) |
| Audio not working | Run `python -c "import sounddevice; print(sounddevice.query_devices())"` and try `--mic-device` |
| Ollama connection refused | Run `ollama serve`; verify with `curl http://localhost:11434/api/tags` |

## Project Structure

```
Halloween/
├── README.md
├── run.sh                    # Launch script (activates venv, runs app)
├── test_components.py        # Verify all components work
├── voices/                   # Piper TTS voice models (.onnx + .onnx.json)
└── .planning/
    ├── crystal_ball.py       # Main application
    ├── requirements.txt      # Python dependencies
    ├── test_microphone.py    # Audio device testing
    ├── led_integration.py    # LED control (WLED/serial/dummy)
    ├── cloud_api_example.py  # Cloud LLM alternative
    ├── parakeet_alternative.py # Alternative STT engine
    └── RESEARCH_NOTES.md     # Background research
```

## Hardware

- **Mini PC:** Ryzen 5 / 16GB RAM (or similar)
- **Microphone:** USB or 3.5mm
- **Speakers:** Any powered speakers
- **Optional:** WS2812B LED strip + ESP8266 with WLED firmware

Expected latency: 2-4 seconds end-to-end (a natural "consulting the spirits" pause).
