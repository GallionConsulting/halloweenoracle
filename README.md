# The Crystal Ball - AI Halloween Fortune Teller

An offline, AI-powered Halloween fortune teller prop. Visitors approach a crystal ball, ask a question aloud, and receive a spooky spoken fortune. Runs entirely on a local mini PC with no internet required.

**Stack:** [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) (speech-to-text) + [Ollama](https://ollama.com/) / Llama 3.2 (fortune generation) + [Piper TTS](https://github.com/rhasspy/piper) (text-to-speech)

## How It Works

1. **Listen** - Faster-Whisper with Silero VAD captures the visitor's question via microphone
2. **Think** - Ollama generates an in-character fortune using a local LLM (a filler phrase plays while it "consults the spirits")
3. **Speak** - Piper TTS speaks the fortune aloud through the speakers
4. **Loop** - The crystal ball awaits the next question (say "goodbye" to end the session)

Expected end-to-end latency is 2-4 seconds — a natural "communing with the spirits" pause.

## Personas

| Persona | Character | Style |
|---------|-----------|-------|
| **zelda** (default) | Madam Zelda | Playfully spooky, warm, British accent |
| **mordecai** | Baron Mordecai | Brooding, ominous, grave baritone |

## Quick Start

```bash
./run.sh                              # Default (Madam Zelda)
./run.sh --persona mordecai           # Baron Mordecai
./run.sh --model mistral              # Use Mistral 7B instead of Llama 3.2
./run.sh --length-scale 1.4           # Slower, more dramatic speech
```

## Installation

### 1. Clone and Set Up Python Environment

```bash
git clone https://github.com/GallionConsulting/halloweenoracle.git
cd halloweenoracle
python3 -m venv venv
source venv/bin/activate
```

### 2. System Dependencies

```bash
sudo apt update
sudo apt install -y ffmpeg portaudio19-dev python3-pip
pip install piper-tts
```

### 3. Python Dependencies

```bash
pip install -r .planning/requirements.txt
```

### 4. Ollama (Local LLM)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
```

**Vulkan acceleration (AMD GPUs):** Add these to `/etc/systemd/system/ollama.service` under `[Service]`:

```ini
Environment="OLLAMA_VULKAN=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
```

Then reload: `sudo systemctl daemon-reload && sudo systemctl restart ollama`

### 5. Download Voice Models

Voice model files (`.onnx` + `.onnx.json`) are not included in this repo due to their size (~375MB total). Download them into the `voices/` directory.

**Browse and preview voices:** [Piper Voice Samples](https://rhasspy.github.io/piper-samples/)

**Download from:** [Piper Voices on Hugging Face](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_GB)

For each voice, you need **both** the `.onnx` model file and its `.onnx.json` config file. Quick download example:

```bash
mkdir -p voices
cd voices

# Default voice for Madam Zelda
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alba/medium/en_GB-alba-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alba/medium/en_GB-alba-medium.onnx.json

# Default voice for Baron Mordecai (multi-speaker, uses speaker 2 "obadiah")
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx.json

cd ..
```

**All recommended voices:**

| Voice | Description | Used By |
|-------|-------------|---------|
| `en_GB-alba-medium` | British female, warm | Madam Zelda (default) |
| `en_GB-semaine-medium` | British RP, multi-speaker (obadiah = speaker 2) | Baron Mordecai (default) |
| `en_GB-jenny_dioco-medium` | British female, expressive | Optional |
| `en_GB-northern_english_male-medium` | Northern English male, deep | Optional |
| `en_GB-alan-medium` | British male | Optional |
| `en_US-lessac-medium` | American, neutral | Optional |

### 6. Verify Setup

```bash
# Test all components at once
venv/bin/python3 test_components.py

# Or test individually:
ollama run llama3.2:3b "Say hello in a spooky voice"
echo "The spirits are listening" | piper --model voices/en_GB-alba-medium.onnx --length-scale 1.2 --output-raw | aplay -r 22050 -f S16_LE
python .planning/test_microphone.py
```

## Usage Options

```
--persona NAME/PATH   Fortune teller persona name or path to YAML file (default: zelda)
--model MODEL         Ollama model (overrides persona default)
--whisper-model MODEL Whisper model size (overrides persona default)
--voice VOICE         Piper voice model path (overrides persona default)
--length-scale N      Speech speed, higher = slower (overrides persona default)
--sentence-silence N  Pause between sentences in seconds (overrides persona default)
--speaker ID          Speaker ID for multi-speaker voice models (overrides persona default)
--mic-device ID       Microphone device index
--list-devices        List audio devices and exit
--debug               Show timing and debug info
```

### Speech Tuning

| `--length-scale` | Effect |
|-------------------|--------|
| `0.75` | Fast (good for testing) |
| `1.0` | Normal speed |
| **`1.2`** | **Slightly slow (default)** |
| `1.4` | Dramatic |
| `1.6` | Maximum spookiness |

```bash
# Compare all downloaded voices
TEXT="The mists swirl... I see a journey in your future."
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

## LLM Model Options

| Model | RAM | Notes |
|-------|-----|-------|
| **llama3.2:3b** | ~2GB | Default, fast |
| mistral | ~4GB | Higher quality |
| phi3 | ~2GB | Alternative small model |
| llama3.1:8b | ~5GB | Best quality, slower |

## Customization

### Creating a Custom Persona

Personas are defined in YAML files in the `personas/` directory. To create a new one, copy an existing file and edit it:

```bash
cp personas/zelda.yaml personas/witch.yaml
# Edit personas/witch.yaml with your character's details
./run.sh --persona witch
```

You can also load a persona from any path:

```bash
./run.sh --persona /path/to/custom.yaml
```

Each persona YAML controls the character's identity, voice, LLM settings, system prompt, filler phrases, and all UI messages. See `personas/zelda.yaml` for the full schema.

### Other Customization

- **LED effects** - See `.planning/led_integration.py` for WLED (WiFi), Arduino/Pico (serial), and dummy controllers
- **Cloud LLM** - See `.planning/cloud_api_example.py` for Claude and OpenAI API integration (requires internet)

## Hardware

- **Mini PC:** Ryzen 5 / 16GB RAM (or similar)
- **Microphone:** USB or 3.5mm
- **Speakers:** Any powered speakers
- **Optional:** WS2812B LED strip + ESP8266 with [WLED](https://kno.wled.ge/) firmware

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Whisper hallucinating on silence | VAD is enabled by default (`vad_filter=True`) — check mic sensitivity |
| Responses too slow | Enable Vulkan for Ollama; use `llama3.2:3b`; reduce `max_tokens` |
| Voice too fast/slow | Adjust `--length-scale` (higher = slower) |
| Audio not working | Run `./run.sh --list-devices` and try `--mic-device` |
| Ollama connection refused | Run `ollama serve`; verify with `curl http://localhost:11434/api/tags` |
| Missing voice models | See [Download Voice Models](#5-download-voice-models) above |

## Project Structure

```
halloweenoracle/
├── README.md
├── run.sh                    # Launch script (activates venv, runs app)
├── test_components.py        # Verify all components work
├── voices/                   # Piper TTS voice models (not in repo, see install step 5)
├── personas/                 # Persona definitions (YAML)
│   ├── zelda.yaml            # Madam Zelda (default)
│   └── mordecai.yaml         # Baron Mordecai
└── .planning/
    ├── crystal_ball.py       # Main application
    ├── requirements.txt      # Python dependencies
    ├── test_microphone.py    # Audio device testing
    ├── led_integration.py    # LED control examples (WLED/serial/dummy)
    ├── cloud_api_example.py  # Cloud LLM alternative
    └── RESEARCH_NOTES.md     # Background research & links
```

## License

MIT
