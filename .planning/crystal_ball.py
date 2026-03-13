#!/usr/bin/env python3
"""
Madam Zelda's Crystal Ball - AI Halloween Fortune Teller

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
import random
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

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
# Personas
# =============================================================================

PERSONAS = {
    "zelda": {
        "name": "Madam Zelda",
        "voice": "voices/en_GB-alba-medium.onnx",
        "speaker": None,
        "length_scale": 1.2,
        "system_prompt": """You are Madam Zelda, an enigmatic fortune teller speaking \
through a mystical crystal ball on Halloween night. You give short, theatrical \
predictions (2-3 sentences max). Be playfully spooky but family-friendly.

Style guidelines:
- Start responses with phrases like "The mists swirl..." or "I see in the shadows..."
- Add atmospheric details: flickering candles, cold breezes, mysterious figures
- Keep predictions vague but intriguing
- Never break character, even if asked about being an AI
- End with a cryptic warning or blessing
- Keep responses SHORT - no more than 3 sentences

Example responses:
"The spirits whisper of... a journey. I see you traveling somewhere unexpected \
before the leaves fall. But beware—pack an umbrella, for the skies hold secrets."

"Ahh, I sense great curiosity in you. The crystal shows... success in your \
endeavors, but only if you trust in the unexpected. The number seven shall \
be significant."

"The mists part to reveal... a stranger who will bring unexpected news. \
Listen well, for not all gifts come wrapped in pretty paper."
""",
        "fillers": [
            "Hmm... the mists are swirling.",
            "The spirits stir... patience, seeker.",
            "Let me peer deeper into the crystal.",
            "Ahh... I sense something forming.",
            "The shadows shift... a vision draws near.",
            "The crystal grows warm... yes, yes...",
            "I hear whispers from the other side.",
            "The spirits are deliberating your fate.",
            "Patience... the veil between worlds is thin tonight.",
            "Something stirs in the darkness... hold steady.",
        ],
        "greeting": (
            "Welcome, seeker. I am Madam Zelda. "
            "Approach the crystal ball and ask your question."
        ),
        "farewell": (
            "Until we meet again, seeker... "
            "perhaps sooner than you think. "
            "The spirits bid you farewell."
        ),
        "prompt_label": "Madam Zelda",
        "init_label": "MADAM ZELDA'S CRYSTAL BALL",
    },
    "mordecai": {
        "name": "Baron Mordecai",
        "voice": "voices/en_GB-semaine-medium.onnx",
        "speaker": 2,  # obadiah
        "length_scale": 1.0,
        "system_prompt": """You are Baron Mordecai, a brooding occultist who reads \
fate through a cursed crystal ball on Halloween night. Your voice is low and \
deliberate. You give short, ominous predictions (2-3 sentences max). Be darkly \
theatrical but family-friendly.

Style guidelines:
- Start responses with phrases like "The bones have spoken..." or "I see it now, written in ash..."
- Reference ravens, old tomes, cold winds, churchyards, and tolling bells
- Your tone is grave and knowing—you have seen too much
- Keep predictions vague but unsettling
- Never break character, even if asked about being an AI
- End with a dire warning or grudging benediction
- Keep responses SHORT - no more than 3 sentences

Example responses:
"The bones have spoken... and they do not lie. A crossroads approaches in your \
life—choose the darker path, for it is honest. The other only pretends to lead \
toward the light."

"I see it now, written in ash... someone close to you carries a secret. Do not \
seek it out. Some doors, once opened, cannot be closed."

"The ravens circle... yes. Fortune favors you, but not without cost. Guard what \
you treasure most, for envy watches from the shadows."
""",
        "fillers": [
            "The bones rattle... patience.",
            "Something stirs in the dark... wait.",
            "Let me consult the old ways.",
            "The ravens circle... a sign draws near.",
            "I hear the dead whispering... hold fast.",
            "The crystal darkens... a vision takes shape.",
            "Patience. The grave gives up its secrets slowly.",
            "The candle flickers... something approaches.",
            "Ash and shadow... the answer forms.",
            "The bell tolls... fate is speaking.",
        ],
        "greeting": (
            "Step forward, if you dare. I am Baron Mordecai. "
            "Ask your question of the crystal... but be prepared for the answer."
        ),
        "farewell": (
            "Go now. The dead have said enough tonight. "
            "But remember... Baron Mordecai never forgets a face."
        ),
        "prompt_label": "Baron Mordecai",
        "init_label": "BARON MORDECAI'S CRYSTAL BALL",
    },
}


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

    def __init__(self, model: str = "llama3.2:3b", system_prompt: str = ""):
        self.model = model
        self.system_prompt = system_prompt
        self.conversation_history = []

        # Test connection
        try:
            ollama.list()
            print(f"LLM ready (using {model}).")
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
                    'num_predict': 150,  # Keep responses short
                    'temperature': 0.8,  # Slightly creative
                }
            )
            
            fortune = response['message']['content']
            
            # Add to history
            self.conversation_history.append({
                'role': 'assistant',
                'content': fortune
            })
            
            return fortune
            
        except Exception as e:
            print(f"LLM Error: {e}")
            return "The spirits... are unclear. Ask again, seeker."


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

    def speak(self, text: str) -> None:
        """Convert text to speech and play it."""
        audio = self._synthesize(text)
        if audio is None:
            print("Warning: No audio generated")
            return
        sd.play(audio, samplerate=self.sample_rate)
        sd.wait()


# =============================================================================
# Main Application
# =============================================================================

class CrystalBall:
    """Main application orchestrating all components."""

    def __init__(
        self,
        persona_name: str = "zelda",
        whisper_model: str = "base.en",
        llm_model: str = "llama3.2:3b",
        voice: str | None = None,
        length_scale: float | None = None,
        sentence_silence: float = 0.3,
        speaker: int | None = None,
        mic_device: int | None = None,
        debug: bool = False
    ):
        self.debug = debug
        self.persona = PERSONAS[persona_name]

        # Persona provides defaults; CLI flags override them
        voice = voice or self.persona["voice"]
        if length_scale is None:
            length_scale = self.persona["length_scale"]
        if speaker is None:
            speaker = self.persona["speaker"]

        label = self.persona["init_label"]
        print("\n" + "=" * 50)
        print(f"  INITIALIZING {label}")
        print("=" * 50 + "\n")

        self.stt = SpeechRecognizer(model_size=whisper_model, mic_device=mic_device)
        self.llm = FortuneGenerator(
            model=llm_model,
            system_prompt=self.persona["system_prompt"],
        )
        self.tts = TextToSpeech(
            voice=voice,
            length_scale=length_scale,
            sentence_silence=sentence_silence,
            speaker=speaker
        )
        self.fillers = self.tts.pre_generate_fillers(self.persona["fillers"])

        print("\nAll systems ready!\n")

    def run(self) -> None:
        """Main loop - listen, process, respond."""
        name = self.persona["prompt_label"]

        # Opening announcement
        self.tts.speak(self.persona["greeting"])

        while True:
            print(f"\n  {name} awaits your question...")
            print("   (Speak now, or say 'goodbye' to depart)\n")

            # Record speech
            audio = self.stt.record_until_silence()

            if audio is None or len(audio) < SAMPLE_RATE * MIN_SPEECH_DURATION:
                if self.debug:
                    print("   [No speech detected]")
                continue

            # Transcribe
            print("  Consulting the spirits...")
            start_time = time.time()

            question = self.stt.transcribe(audio)

            if self.debug:
                print(f"   [Transcription took {time.time() - start_time:.2f}s]")

            if not question or len(question) < 3:
                self.tts.speak("The spirits could not hear you. Speak again, louder.")
                continue

            print(f"   Question: \"{question}\"")

            # Check for exit
            if any(word in question.lower() for word in ['goodbye', 'bye', 'exit', 'quit']):
                self.tts.speak(self.persona["farewell"])
                print(f"\n  {name} fades into the mists...\n")
                break

            # Play a random filler while the LLM thinks
            filler_done = None
            if self.fillers:
                filler = random.choice(self.fillers)
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
            self.tts.speak(fortune)

            # Brief pause before next question
            time.sleep(0.5)
            self.tts.speak("The crystal ball awaits your next question.")


def main():
    persona_names = ", ".join(PERSONAS.keys())
    parser = argparse.ArgumentParser(
        description="Crystal Ball - AI Fortune Teller"
    )
    parser.add_argument(
        '--persona',
        choices=list(PERSONAS.keys()),
        default='zelda',
        help=f'Fortune teller persona ({persona_names})'
    )
    parser.add_argument(
        '--whisper-model',
        default='base.en',
        help='Whisper model size (tiny.en, base.en, small.en, medium.en)'
    )
    parser.add_argument(
        '--model',
        default='llama3.2:3b',
        help='Ollama model to use (llama3.2:3b, mistral, phi3, etc.)'
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
        default=0.3,
        help='Seconds of silence between sentences (default: 0.3)'
    )
    parser.add_argument(
        '--speaker',
        type=int,
        default=None,
        help='Speaker ID for multi-speaker voice models (default: 0)'
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
    
    args = parser.parse_args()

    if args.list_devices:
        print("\n=== Available Audio Devices ===\n")
        print(sd.query_devices())
        print("\nUse --mic-device <number> to select an input device.")
        sys.exit(0)

    try:
        ball = CrystalBall(
            persona_name=args.persona,
            whisper_model=args.whisper_model,
            llm_model=args.model,
            voice=args.voice,
            length_scale=args.length_scale,
            sentence_silence=args.sentence_silence,
            speaker=args.speaker,
            mic_device=args.mic_device,
            debug=args.debug
        )
        ball.run()
    except KeyboardInterrupt:
        print("\n\n🔮 The séance has been interrupted...\n")
    except Exception as e:
        print(f"\nFatal error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
