#!/usr/bin/env python3
"""
Crystal Ball - AI Halloween Fortune Teller

A standalone interactive fortune teller using:
- Faster-Whisper for speech recognition (with Silero VAD)
- Ollama for local LLM inference
- Piper for text-to-speech

Usage:
    python crystal_ball.py
    python crystal_ball.py --model llama3.2:3b --debug
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

import yaml

from led_integration import create_led_controller

import numpy as np
import sounddevice as sd

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Error: faster-whisper not installed. Run: pip install faster-whisper")
    sys.exit(1)

try:
    import ollama
except ImportError:
    print("Error: ollama not installed. Run: pip install ollama")
    sys.exit(1)


# =============================================================================
# Configuration
# =============================================================================

SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01      # Adjust based on your mic sensitivity
SILENCE_DURATION = 1.5        # Seconds of silence to stop recording
MAX_DURATION = 15             # Max recording length in seconds
MIN_SPEECH_DURATION = 0.5     # Minimum speech to process

# =============================================================================
# Persona Loading
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PERSONAS_DIR = SCRIPT_DIR / "personas"

REQUIRED_FIELDS = [
    "name", "prompt_label", "init_label",
    "voice", "length_scale", "sentence_silence",
    "llm_model", "whisper_model", "temperature", "num_predict",
    "system_prompt", "greeting", "farewell", "fillers", "messages",
]
REQUIRED_MESSAGES = [
    "consulting", "no_speech", "next_question", "awaiting",
    "speak_now", "departed", "llm_error", "interrupted",
]


def list_available_personas() -> list[str]:
    """Return bare names of persona YAML files in the personas/ directory."""
    if not PERSONAS_DIR.is_dir():
        return []
    return sorted(p.stem for p in PERSONAS_DIR.glob("*.yaml"))


def load_persona(name: str) -> dict:
    """Load a persona from a YAML file.

    Accepts a bare name (e.g. 'zelda' -> personas/zelda.yaml relative to
    the script directory) or a path to a YAML file.
    """
    path = Path(name)
    if not path.suffix:
        path = PERSONAS_DIR / f"{name}.yaml"

    if not path.is_file():
        available = list_available_personas()
        msg = f"Persona file not found: {path}"
        if available:
            msg += f"\nAvailable personas: {', '.join(available)}"
        else:
            msg += f"\nNo persona files found in {PERSONAS_DIR}"
        print(msg)
        sys.exit(1)

    with open(path) as f:
        persona = yaml.safe_load(f)

    # Validate required top-level fields
    missing = [k for k in REQUIRED_FIELDS if k not in persona]
    if missing:
        print(f"Persona {path.name} is missing required fields: {', '.join(missing)}")
        sys.exit(1)

    # Validate required message keys
    missing_msgs = [k for k in REQUIRED_MESSAGES if k not in persona.get("messages", {})]
    if missing_msgs:
        print(f"Persona {path.name} is missing required messages: {', '.join(missing_msgs)}")
        sys.exit(1)

    return persona


# =============================================================================
# Speech-to-Text
# =============================================================================

class SpeechRecognizer:
    """Handles speech recording and transcription."""
    
    def __init__(self, model_size: str = "base.en", device: str = "cpu", mic_device: int | None = None):
        self.mic_device = mic_device
        print(f"Loading Whisper model ({model_size})...")
        self.model = WhisperModel(model_size, device=device, compute_type="int8")
        if mic_device is not None:
            dev_info = sd.query_devices(mic_device)
            print(f"Speech recognition ready (mic: {dev_info['name']}).")
        else:
            print("Speech recognition ready (mic: system default).")
    
    def record_until_silence(self) -> np.ndarray | None:
        """Record audio until silence is detected after speech."""
        frames = []
        silent_chunks = 0
        chunk_duration = 0.1
        chunk_samples = int(SAMPLE_RATE * chunk_duration)
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
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='float32',
            callback=callback,
            blocksize=chunk_samples,
            device=self.mic_device
        ):
            while recording:
                sd.sleep(100)
        
        if not frames:
            return None
        
        audio = np.concatenate(frames, axis=0)
        return audio.flatten()
    
    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio using Whisper with VAD filtering."""
        # Save to temp file (faster-whisper needs file input)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            with wave.open(temp_path, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes((audio * 32767).astype(np.int16).tobytes())
            
            try:
                segments, _ = self.model.transcribe(
                    temp_path,
                    vad_filter=True,  # Enable Silero VAD
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
                text = " ".join(segment.text for segment in segments)
            finally:
                os.unlink(temp_path)
        
        return text.strip()


# =============================================================================
# LLM Fortune Generation
# =============================================================================

class FortuneGenerator:
    """Generates fortunes using local LLM via Ollama."""

    def __init__(
        self,
        model: str = "llama3.2:3b",
        system_prompt: str = "",
        temperature: float = 0.8,
        num_predict: int = 150,
        llm_error_message: str = "",
        debug: bool = False,
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.num_predict = num_predict
        self.llm_error_message = llm_error_message
        self.debug = debug
        self.conversation_history = []

        # Test connection and validate model
        try:
            response = ollama.list()
            available_models = [m.model for m in response.models]
            if model not in available_models:
                # Also check without :latest suffix
                alt = model if ':' in model else f"{model}:latest"
                if alt not in available_models:
                    print(f"\nError: Model '{model}' not found in Ollama.")
                    if available_models:
                        print(f"  Available models: {', '.join(sorted(available_models))}")
                    print(f"\n  To fix: ollama pull {model}")
                    raise RuntimeError(f"Model '{model}' not available")
            # Pre-load the model into memory so the first query is fast
            print(f"Pre-loading {model} into memory...")
            ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': 'hello'}],
                options={'num_predict': 1},
            )
            print(f"LLM ready (using {model}).")
        except RuntimeError:
            raise
        except Exception as e:
            print(f"Error: Cannot connect to Ollama. Is it running?")
            print(f"  Start with: ollama serve")
            print(f"  Then pull model: ollama pull {model}")
            raise

    def generate(self, question: str) -> str:
        """Generate a fortune based on the question."""
        # Add to history for context (optional - remove for stateless)
        self.conversation_history.append({
            'role': 'user',
            'content': question
        })

        # Keep only last few exchanges to avoid context overflow
        recent_history = self.conversation_history[-6:]

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': self.system_prompt},
                    *recent_history
                ],
                options={
                    'num_predict': self.num_predict,
                    'temperature': self.temperature,
                }
            )

            fortune = response['message']['content']

            # Strip <think>...</think> blocks (e.g. qwen3 thinking mode)
            raw_fortune = fortune
            fortune = re.sub(r'<think>[\s\S]*?</think>', '', fortune)
            # Handle unclosed <think> tag (truncated output)
            fortune = re.sub(r'<think>[\s\S]*$', '', fortune)
            # Strip markdown emphasis (*/_) so TTS doesn't say "asterisk"
            fortune = re.sub(r'(\*{1,3}|_{1,3})(.+?)\1', r'\2', fortune)
            # Strip emojis so TTS doesn't try to read them
            fortune = re.sub(
                r'[\U0001F600-\U0001F64F'   # emoticons
                r'\U0001F300-\U0001F5FF'     # misc symbols & pictographs
                r'\U0001F680-\U0001F6FF'     # transport & map symbols
                r'\U0001F1E0-\U0001F1FF'     # flags
                r'\U0001F900-\U0001F9FF'     # supplemental symbols
                r'\U0001FA00-\U0001FA6F'     # chess symbols & extended-A
                r'\U0001FA70-\U0001FAFF'     # symbols & pictographs extended-A
                r'\U00002702-\U000027B0'     # dingbats
                r'\U0000FE00-\U0000FE0F'     # variation selectors
                r'\U0000200D'                # zero-width joiner
                r'\U000020E3'                # combining enclosing keycap
                r'\U00002600-\U000026FF'     # misc symbols (sun, stars, etc.)
                r'\U00002300-\U000023FF'     # misc technical
                r']+', '', fortune)
            # Replace ellipses with commas so TTS pauses naturally
            fortune = fortune.replace('...', ',')
            fortune = fortune.strip()

            if raw_fortune != fortune and self.debug:
                print(f"   [Cleaned LLM response (think tags / markdown / emojis)]")

            if not fortune:
                print("Warning: LLM response was empty after stripping <think> tags")
                return self.llm_error_message

            # Add to history
            self.conversation_history.append({
                'role': 'assistant',
                'content': fortune
            })

            return fortune

        except Exception as e:
            print(f"LLM Error: {e}")
            return self.llm_error_message


# =============================================================================
# Text-to-Speech
# =============================================================================

class TextToSpeech:
    """Handles text-to-speech using Piper."""

    def __init__(
        self,
        voice: str = "en_GB-alba-medium",
        length_scale: float = 1.2,
        sentence_silence: float = 0.3,
        speaker: int | None = None
    ):
        self.voice = voice
        self.length_scale = length_scale
        self.sentence_silence = sentence_silence
        self.speaker = speaker
        self.sample_rate = 22050  # Piper's default

        # Warn if the voice model file doesn't exist
        voice_path = Path(voice)
        if not voice_path.is_absolute():
            voice_path = SCRIPT_DIR / voice
        if not voice_path.is_file():
            print(f"Warning: Voice model not found: {voice_path}")
            print("  TTS will likely fail. Check the 'voice' field in your persona YAML.")

        # Test Piper availability
        try:
            result = subprocess.run(
                ['piper', '--help'],
                capture_output=True,
                timeout=5
            )
            parts = [f"voice: {voice}"]
            if length_scale != 1.0:
                parts.append(f"speed: {length_scale}")
            if speaker is not None:
                parts.append(f"speaker: {speaker}")
            print(f"TTS ready ({', '.join(parts)}).")
        except FileNotFoundError:
            print("Error: Piper not found. Install with: pip install piper-tts")
            raise

    def _synthesize(self, text: str) -> np.ndarray | None:
        """Synthesize text to a numpy audio array without playing it."""
        try:
            cmd = ['piper', '--model', self.voice, '--output-raw']
            if self.length_scale != 1.0:
                cmd += ['--length-scale', str(self.length_scale)]
            if self.sentence_silence > 0:
                cmd += ['--sentence-silence', str(self.sentence_silence)]
            if self.speaker is not None:
                cmd += ['--speaker', str(self.speaker)]

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            audio_data, _ = process.communicate(text.encode(), timeout=30)

            if not audio_data:
                return None

            return np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768
        except Exception as e:
            print(f"TTS synthesis error: {e}")
            return None

    def pre_generate_fillers(self, phrases: list[str]) -> list[np.ndarray]:
        """Pre-render filler phrases to audio arrays for instant playback."""
        print("Pre-generating filler phrases...")
        fillers = []
        for phrase in phrases:
            audio = self._synthesize(phrase)
            if audio is not None:
                fillers.append(audio)
        if len(fillers) == 0 and len(phrases) > 0:
            print("Warning: All filler phrase TTS failed — fillers will be skipped")
        else:
            print(f"  {len(fillers)} filler clips ready.")
        return fillers

    def play_filler(self, filler: np.ndarray) -> threading.Event:
        """Play a pre-rendered filler clip. Returns an Event that is set when done."""
        done_event = threading.Event()

        def _play():
            sd.play(filler, samplerate=self.sample_rate)
            sd.wait()
            done_event.set()

        thread = threading.Thread(target=_play, daemon=True)
        thread.start()
        return done_event

    def speak(self, text: str) -> bool:
        """Convert text to speech and play it. Returns True on success."""
        audio = self._synthesize(text)
        if audio is None:
            snippet = text[:60] + ("..." if len(text) > 60 else "")
            print(f"Warning: TTS failed for: {snippet}")
            return False
        sd.play(audio, samplerate=self.sample_rate)
        sd.wait()
        return True


# =============================================================================
# Main Application
# =============================================================================

class CrystalBall:
    """Main application orchestrating all components."""

    def __init__(
        self,
        persona: dict,
        mic_device: int | None = None,
        debug: bool = False,
        led_type: str = "dummy",
        wled_host: str = "192.168.1.100",
    ):
        self.debug = debug
        self.persona = persona
        self.messages = persona["messages"]

        label = persona["init_label"]
        print("\n" + "=" * 50)
        print(f"  INITIALIZING {label}")
        print("=" * 50 + "\n")

        self.stt = SpeechRecognizer(
            model_size=persona["whisper_model"],
            mic_device=mic_device,
        )
        self.llm = FortuneGenerator(
            model=persona["llm_model"],
            system_prompt=persona["system_prompt"],
            temperature=persona["temperature"],
            num_predict=persona["num_predict"],
            llm_error_message=persona["messages"]["llm_error"],
            debug=debug,
        )
        self.tts = TextToSpeech(
            voice=persona["voice"],
            length_scale=persona["length_scale"],
            sentence_silence=persona["sentence_silence"],
            speaker=persona["speaker"],
        )
        self.leds = create_led_controller(
            controller_type=led_type,
            debug=debug,
            host=wled_host,
        )
        self.fillers = self.tts.pre_generate_fillers(persona["fillers"])
        self.filler_index = 0

        print("\nAll systems ready!\n")

    def _msg(self, key: str) -> str:
        """Return a message string with {name} substituted."""
        return self.messages[key].format(name=self.persona["prompt_label"])

    def run(self) -> None:
        """Main loop - listen, process, respond."""
        # Opening announcement
        if not self.tts.speak(self.persona["greeting"]):
            print("Warning: Greeting TTS failed — check voice model path")
        self.leds.idle()

        while True:
            print(f"\n  {self._msg('awaiting')}")
            print(f"   {self._msg('speak_now')}\n")

            # Record speech
            self.leds.listening()
            audio = self.stt.record_until_silence()

            if audio is None or len(audio) < SAMPLE_RATE * MIN_SPEECH_DURATION:
                if self.debug:
                    print("   [No speech detected]")
                self.leds.idle()
                continue

            # Transcribe
            print(f"  {self._msg('consulting')}")
            self.leds.thinking()
            start_time = time.time()

            question = self.stt.transcribe(audio)

            if self.debug:
                print(f"   [Transcription took {time.time() - start_time:.2f}s]")

            if not question or len(question) < 3:
                self.tts.speak(self._msg("no_speech"))
                self.leds.idle()
                continue

            print(f"   Question: \"{question}\"")

            # Check for exit
            if any(word in question.lower() for word in ['goodbye', 'bye', 'exit', 'quit']):
                self.leds.goodbye()
                self.tts.speak(self.persona["farewell"])
                print(f"\n  {self._msg('departed')}\n")
                break

            # Play the next filler while the LLM thinks (cycles 1 through N)
            filler_done = None
            if self.fillers:
                filler = self.fillers[self.filler_index]
                self.filler_index = (self.filler_index + 1) % len(self.fillers)
                filler_done = self.tts.play_filler(filler)

            # Generate fortune (runs while filler plays)
            start_time = time.time()
            fortune = self.llm.generate(question)

            if self.debug:
                print(f"   [LLM took {time.time() - start_time:.2f}s]")

            # Wait for filler to finish before speaking the fortune
            if filler_done is not None:
                filler_done.wait()
                time.sleep(0.3)

            print(f"\n   {fortune}\n")

            # Speak the fortune
            self.leds.dramatic_reveal()
            self.tts.speak(fortune)

            # Brief pause before next question
            time.sleep(0.5)
            self.tts.speak(self._msg("next_question"))
            self.leds.idle()


def main():
    available = list_available_personas()
    persona_list = ", ".join(available) if available else "(none found)"
    parser = argparse.ArgumentParser(
        description="Crystal Ball - AI Fortune Teller"
    )
    parser.add_argument(
        '--persona',
        default='zelda',
        help=f'Fortune teller persona name or path to YAML file ({persona_list})'
    )
    parser.add_argument(
        '--whisper-model',
        default=None,
        help='Whisper model size (overrides persona default)'
    )
    parser.add_argument(
        '--model',
        default=None,
        help='Ollama model to use (overrides persona default)'
    )
    parser.add_argument(
        '--voice',
        default=None,
        help='Piper voice model (overrides persona default)'
    )
    parser.add_argument(
        '--length-scale',
        type=float,
        default=None,
        help='Speech speed (overrides persona default, higher=slower, e.g. 1.0 for normal)'
    )
    parser.add_argument(
        '--sentence-silence',
        type=float,
        default=None,
        help='Seconds of silence between sentences (overrides persona default)'
    )
    parser.add_argument(
        '--speaker',
        type=int,
        default=None,
        help='Speaker ID for multi-speaker voice models (overrides persona default)'
    )
    parser.add_argument(
        '--mic-device',
        type=int,
        default=None,
        help='Microphone device index (run with --list-devices to see options)'
    )
    parser.add_argument(
        '--list-devices',
        action='store_true',
        help='List available audio devices and exit'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    parser.add_argument(
        '--led-type',
        default='dummy',
        choices=['wled', 'serial', 'dummy', 'auto'],
        help='LED controller type (default: dummy)'
    )
    parser.add_argument(
        '--wled-host',
        default='192.168.1.100',
        help='WLED device IP address (default: 192.168.1.100)'
    )
    parser.add_argument(
        '--no-leds',
        action='store_true',
        help='Disable LEDs (same as --led-type dummy)'
    )

    args = parser.parse_args()

    if args.list_devices:
        print("\n=== Available Audio Devices ===\n")
        print(sd.query_devices())
        print("\nUse --mic-device <number> to select an input device.")
        sys.exit(0)

    # Load persona and apply CLI overrides
    persona = load_persona(args.persona)
    if args.voice is not None:
        persona["voice"] = args.voice
    if args.length_scale is not None:
        persona["length_scale"] = args.length_scale
    if args.sentence_silence is not None:
        persona["sentence_silence"] = args.sentence_silence
    if args.speaker is not None:
        persona["speaker"] = args.speaker
    if args.model is not None:
        persona["llm_model"] = args.model
    if args.whisper_model is not None:
        persona["whisper_model"] = args.whisper_model

    led_type = 'dummy' if args.no_leds else args.led_type

    try:
        ball = CrystalBall(
            persona=persona,
            mic_device=args.mic_device,
            debug=args.debug,
            led_type=led_type,
            wled_host=args.wled_host,
        )
        ball.run()
    except KeyboardInterrupt:
        print(f"\n\n{persona['messages']['interrupted']}\n")
    except Exception as e:
        print(f"\nFatal error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
