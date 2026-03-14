#!/usr/bin/env python3
"""
LED Integration for Crystal Ball

This file provides LED controller classes for the crystal ball project.
The primary focus is WLED, which offers the best balance of flexibility,
built-in effects, and ease of setup.

Controllers included:
1. WLEDController (Recommended) - WiFi control via JSON API
2. SerialLEDController - Arduino/Pico via USB serial
3. DummyLEDController - For testing without hardware

WLED Setup:
-----------
1. Get a WLED-compatible controller (ESP8266/ESP32 with USB-C)
2. Flash WLED firmware: https://install.wled.me/
3. Connect your LED strip (WS2812B/NeoPixel)
4. Configure WiFi and note the IP address
5. Update WLED_HOST in this file or pass to constructor
"""

import json
import time
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# Abstract Base Class
# =============================================================================

class LEDController(ABC):
    """Base class for LED controllers."""
    
    @abstractmethod
    def idle(self):
        """Idle animation while waiting for input."""
        pass
    
    @abstractmethod
    def listening(self):
        """Animation while recording speech."""
        pass
    
    @abstractmethod
    def thinking(self):
        """Animation while processing/generating response."""
        pass
    
    @abstractmethod
    def speaking(self):
        """Animation while speaking the fortune."""
        pass
    
    @abstractmethod
    def dramatic_reveal(self):
        """Brief dramatic effect before speaking fortune."""
        pass
    
    @abstractmethod
    def goodbye(self):
        """Farewell animation when session ends."""
        pass


# =============================================================================
# WLED Effect Reference
# =============================================================================

@dataclass
class WLEDEffect:
    """WLED effect definition with recommended settings."""
    id: int
    name: str
    speed: int = 128      # 0-255, 128 is default
    intensity: int = 128  # 0-255, effect-specific
    palette: int = 0      # Color palette ID


# Curated effects that work well for the crystal ball
# Full list: https://kno.wled.ge/features/effects/
WLED_EFFECTS = {
    # Mystical/Ambient effects
    'breathe': WLEDEffect(2, "Breathe", speed=60, intensity=128),
    'candle': WLEDEffect(88, "Candle", speed=128, intensity=192),
    'fire_flicker': WLEDEffect(45, "Fire Flicker", speed=100, intensity=180),
    'aurora': WLEDEffect(38, "Aurora", speed=80, intensity=128),
    'fairy': WLEDEffect(160, "Fairy", speed=100, intensity=200),
    'fairytwinkle': WLEDEffect(161, "Fairytwinkle", speed=80, intensity=180),
    'flow': WLEDEffect(110, "Flow", speed=70, intensity=128),
    
    # Active/Alert effects
    'pulse': WLEDEffect(2, "Breathe", speed=180, intensity=255),  # Fast breathe
    'chase': WLEDEffect(28, "Chase", speed=150, intensity=128),
    'theater_chase': WLEDEffect(14, "Theater Chase", speed=128, intensity=128),
    'running': WLEDEffect(15, "Running", speed=100, intensity=128),
    'twinkle': WLEDEffect(55, "Twinkle", speed=100, intensity=128),
    'sparkle': WLEDEffect(52, "Sparkle", speed=128, intensity=200),
    
    # Dramatic effects
    'flash_sparkle': WLEDEffect(54, "Flash Sparkle", speed=200, intensity=255),
    'fire_2012': WLEDEffect(66, "Fire 2012", speed=128, intensity=200),
    'lightning': WLEDEffect(57, "Lightning", speed=128, intensity=128),
    'dissolve': WLEDEffect(18, "Dissolve", speed=128, intensity=128),
    
    # Solid/Simple
    'solid': WLEDEffect(0, "Solid", speed=128, intensity=128),
    'fade': WLEDEffect(1, "Blink", speed=30, intensity=128),  # Slow blink = fade
}

# Color palettes that work well for fortune teller theme
# Full list: https://kno.wled.ge/features/palettes/
WLED_PALETTES = {
    'default': 0,
    'rainbow': 11,
    'purple_blue': 23,    # Party colors
    'fire': 35,           # Heat colors
    'ocean': 8,
    'forest': 10,
    'lava': 36,
    'sunset': 28,
    'fairy_reef': 41,     # Pinks and purples
    'semi_blue': 42,
    'aurora': 50,
}


# =============================================================================
# WLED Controller (Recommended)
# =============================================================================

class WLEDController(LEDController):
    """
    Control LEDs via WLED firmware over WiFi.
    
    WLED is the recommended approach because:
    - Many built-in effects (no animation code needed)
    - Easy web-based configuration
    - Reliable and well-maintained
    - Works with cheap ESP8266/ESP32 boards
    - USB-C powered integrated modules available
    
    Setup:
        1. Flash WLED: https://install.wled.me/
        2. Connect to WLED's WiFi AP and configure your network
        3. Note the IP address assigned to the device
        4. Pass that IP to this controller
    
    API Documentation: https://kno.wled.ge/interfaces/json-api/
    """
    
    def __init__(
        self, 
        host: str = '192.168.1.100',
        timeout: float = 2.0,
        brightness: int = 150,
        transition_time: float = 0.5
    ):
        """
        Initialize WLED controller.
        
        Args:
            host: IP address or hostname of WLED device
            timeout: HTTP request timeout in seconds
            brightness: Default brightness (0-255)
            transition_time: Default transition time in seconds
        """
        self.host = host
        self.base_url = f'http://{host}/json'
        self.timeout = timeout
        self.default_brightness = brightness
        self.default_transition = int(transition_time * 10)  # WLED uses deciseconds
        
        # Color presets for different states (RGB)
        self.colors = {
            'idle': [128, 0, 255],       # Purple - mystical
            'listening': [0, 255, 128],   # Cyan-green - receptive
            'thinking': [0, 100, 255],    # Blue - processing
            'speaking': [255, 100, 0],    # Warm orange - fire/candle
            'dramatic': [255, 255, 255],  # White flash
            'goodbye': [100, 0, 150],     # Deep purple - fading
        }
        
        # Test connection
        if self._test_connection():
            print(f"✅ WLED controller connected at {host}")
            self._get_info()
        else:
            print(f"⚠️  WLED controller at {host} not responding")
            print("   Will retry on each command")
    
    def _test_connection(self) -> bool:
        """Test if WLED device is reachable."""
        try:
            req = urllib.request.Request(f'{self.base_url}/state', method='GET')
            urllib.request.urlopen(req, timeout=self.timeout)
            return True
        except Exception:
            return False

    def _get_info(self):
        """Get and display WLED device info."""
        try:
            req = urllib.request.Request(f'{self.base_url}/info', method='GET')
            response = urllib.request.urlopen(req, timeout=self.timeout)
            info = json.loads(response.read())
            led_count = info.get('leds', {}).get('count', '?')
            version = info.get('ver', '?')
            name = info.get('name', 'WLED')
            print(f"   Device: {name}, LEDs: {led_count}, Version: {version}")
        except Exception:
            pass
    
    def _send(self, data: dict) -> bool:
        """
        Send state update to WLED.
        
        Args:
            data: Dictionary of state parameters
            
        Returns:
            True if successful, False otherwise
        """
        # Add default transition if not specified
        if 'transition' not in data:
            data['transition'] = self.default_transition
        
        try:
            req = urllib.request.Request(
                f'{self.base_url}/state',
                data=json.dumps(data).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=self.timeout)
            return True
        except urllib.error.URLError as e:
            print(f"   [WLED connection error: {e}]")
            return False
        except Exception as e:
            print(f"   [WLED error: {e}]")
            return False
    
    def _set_effect(
        self,
        effect: WLEDEffect,
        color: list,
        brightness: Optional[int] = None,
        palette: Optional[int] = None
    ):
        """
        Set a WLED effect with color.
        
        Args:
            effect: WLEDEffect definition
            color: Primary RGB color [r, g, b]
            brightness: Override default brightness
            palette: Override effect's default palette
        """
        self._send({
            "on": True,
            "bri": brightness or self.default_brightness,
            "seg": [{
                "fx": effect.id,
                "sx": effect.speed,      # Speed
                "ix": effect.intensity,  # Intensity
                "pal": palette if palette is not None else effect.palette,
                "col": [color]           # Primary color
            }]
        })
    
    # -------------------------------------------------------------------------
    # State Methods
    # -------------------------------------------------------------------------
    
    def idle(self):
        """
        Idle state - slow mystical pulse.
        
        Purple breathing effect, calm and mysterious.
        Like the crystal ball gently glowing, waiting.
        """
        self._set_effect(
            WLED_EFFECTS['breathe'],
            self.colors['idle'],
            brightness=100  # Dimmer for idle
        )
    
    def listening(self):
        """
        Listening state - attentive glow.
        
        Brighter, slightly animated to show it's "awake"
        and paying attention to the speaker.
        """
        self._set_effect(
            WLED_EFFECTS['fairy'],
            self.colors['listening'],
            brightness=180
        )
    
    def thinking(self):
        """
        Thinking state - mystical processing.
        
        Swirling/flowing effect in blue tones.
        "The spirits are being consulted..."
        """
        self._set_effect(
            WLED_EFFECTS['aurora'],
            self.colors['thinking'],
            brightness=200,
            palette=WLED_PALETTES['purple_blue']
        )
    
    def speaking(self):
        """
        Speaking state - warm ethereal glow.
        
        Candle-like flickering in warm tones.
        As if the crystal ball is channeling energy.
        """
        self._set_effect(
            WLED_EFFECTS['candle'],
            self.colors['speaking'],
            brightness=220
        )
    
    def dramatic_reveal(self):
        """
        Dramatic reveal - brief flash before fortune.
        
        Quick bright flash then settle into speaking state.
        "The spirits have spoken!"
        """
        # Quick flash
        self._send({
            "on": True,
            "bri": 255,
            "transition": 1,  # Very fast
            "seg": [{
                "fx": WLED_EFFECTS['solid'].id,
                "col": [self.colors['dramatic']]
            }]
        })
        time.sleep(0.3)
        
        # Transition to speaking
        self.speaking()
    
    def goodbye(self):
        """
        Goodbye state - fade out effect.
        
        Slow dissolve/fade to darkness.
        "Until we meet again..."
        """
        self._set_effect(
            WLED_EFFECTS['dissolve'],
            self.colors['goodbye'],
            brightness=150
        )
        time.sleep(2)
        
        # Fade to off
        self._send({
            "on": True,
            "bri": 30,
            "transition": 30  # 3 second fade
        })
        time.sleep(3)
        self._send({"on": False})
    
    # -------------------------------------------------------------------------
    # Additional Utility Methods
    # -------------------------------------------------------------------------
    
    def set_color(self, r: int, g: int, b: int, brightness: Optional[int] = None):
        """Set a solid color."""
        self._send({
            "on": True,
            "bri": brightness or self.default_brightness,
            "seg": [{"fx": 0, "col": [[r, g, b]]}]
        })
    
    def off(self):
        """Turn off LEDs."""
        self._send({"on": False})
    
    def on(self):
        """Turn on LEDs (restore previous state)."""
        self._send({"on": True})
    
    def set_brightness(self, brightness: int):
        """Set brightness (0-255)."""
        self._send({"bri": min(255, max(0, brightness))})
    
    def preview_effect(self, effect_name: str):
        """Preview a named effect for testing."""
        if effect_name in WLED_EFFECTS:
            effect = WLED_EFFECTS[effect_name]
            print(f"Previewing: {effect.name}")
            self._set_effect(effect, self.colors['idle'])
        else:
            print(f"Unknown effect: {effect_name}")
            print(f"Available: {', '.join(WLED_EFFECTS.keys())}")


# =============================================================================
# Serial LED Controller (Arduino/Pico alternative)
# =============================================================================

class SerialLEDController(LEDController):
    """
    Control LEDs via Arduino or Raspberry Pi Pico connected over USB serial.
    
    This is a simpler alternative if you don't want WiFi, but requires
    writing your own animation code on the microcontroller.
    
    Protocol: Single character commands
    - 'I' = idle
    - 'L' = listening  
    - 'T' = thinking
    - 'S' = speaking
    - 'D' = dramatic
    - 'G' = goodbye
    """
    
    def __init__(self, port: str = '/dev/ttyUSB0', baud: int = 9600):
        try:
            import serial
            self.serial = serial.Serial(port, baud, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            print(f"✅ Serial LED controller connected on {port}")
        except ImportError:
            print("pyserial not installed. Run: pip install pyserial")
            raise
        except Exception as e:
            print(f"Failed to connect to serial port {port}: {e}")
            raise
    
    def _send(self, command: str):
        self.serial.write(command.encode())
    
    def idle(self):
        self._send('I')
    
    def listening(self):
        self._send('L')
    
    def thinking(self):
        self._send('T')
    
    def speaking(self):
        self._send('S')
    
    def dramatic_reveal(self):
        self._send('D')
        time.sleep(0.5)
    
    def goodbye(self):
        self._send('G')


# =============================================================================
# Dummy Controller (for testing)
# =============================================================================

class DummyLEDController(LEDController):
    """Dummy controller that prints state changes for testing."""
    
    def __init__(self):
        print("✅ Using dummy LED controller (no hardware)")
    
    def idle(self):
        print("   💡 [LED: idle - purple pulse]")
    
    def listening(self):
        print("   💡 [LED: listening - green glow]")
    
    def thinking(self):
        print("   💡 [LED: thinking - blue swirl]")
    
    def speaking(self):
        print("   💡 [LED: speaking - warm flicker]")
    
    def dramatic_reveal(self):
        print("   💡 [LED: ✨ FLASH! ✨]")
        time.sleep(0.3)
    
    def goodbye(self):
        print("   💡 [LED: fading to darkness...]")


# =============================================================================
# Factory Function
# =============================================================================

def create_led_controller(
    controller_type: str = 'auto',
    **kwargs
) -> LEDController:
    """
    Create an LED controller based on type or auto-detect.
    
    Args:
        controller_type: 'wled', 'serial', 'dummy', or 'auto'
        **kwargs: Passed to controller constructor
        
    Returns:
        LEDController instance
    """
    if controller_type == 'dummy':
        return DummyLEDController()
    
    if controller_type == 'wled':
        return WLEDController(**kwargs)
    
    if controller_type == 'serial':
        return SerialLEDController(**kwargs)
    
    if controller_type == 'auto':
        # Try WLED first
        wled_host = kwargs.get('host', '192.168.1.100')
        try:
            controller = WLEDController(host=wled_host, **kwargs)
            if controller._test_connection():
                return controller
        except Exception:
            pass

        # Try serial
        for port in ['/dev/ttyUSB0', '/dev/ttyACM0', 'COM3', 'COM4']:
            try:
                return SerialLEDController(port=port)
            except Exception:
                continue
        
        # Fall back to dummy
        print("No LED hardware found, using dummy controller")
        return DummyLEDController()
    
    raise ValueError(f"Unknown controller type: {controller_type}")


# =============================================================================
# Integration Example
# =============================================================================

INTEGRATION_EXAMPLE = '''
# ============================================================
# How to integrate LEDs with crystal_ball.py
# ============================================================

# 1. Add import at top of crystal_ball.py:
from led_integration import create_led_controller

# 2. In CrystalBall.__init__, add:
self.leds = create_led_controller(
    controller_type='wled',  # or 'auto'
    host='192.168.1.100'     # Your WLED IP
)
self.leds.idle()

# 3. In CrystalBall.run(), add LED state changes:

def run(self):
    self.leds.idle()
    self.tts.speak("Welcome, seeker...")
    
    while True:
        print("Listening...")
        self.leds.listening()  # 👈 Add
        
        audio = self.stt.record_until_silence()
        
        if audio is None:
            self.leds.idle()   # 👈 Add
            continue
        
        self.leds.thinking()   # 👈 Add
        question = self.stt.transcribe(audio)
        
        if "goodbye" in question.lower():
            self.leds.goodbye()  # 👈 Add
            self.tts.speak("Until we meet again...")
            break
        
        fortune = self.llm.generate(question)
        
        self.leds.dramatic_reveal()  # 👈 Add (optional flash)
        # speaking state is set by dramatic_reveal
        
        self.tts.speak(fortune)
        
        self.leds.idle()  # 👈 Add

# ============================================================
'''


# =============================================================================
# CLI for Testing
# =============================================================================

def main():
    """Command-line interface for testing LED effects."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test LED controller')
    parser.add_argument('--host', default='192.168.1.100', help='WLED IP address')
    parser.add_argument('--type', default='auto', choices=['wled', 'serial', 'dummy', 'auto'])
    parser.add_argument('--demo', action='store_true', help='Run demo sequence')
    parser.add_argument('--effect', help='Preview specific effect')
    parser.add_argument('--list-effects', action='store_true', help='List available effects')
    
    args = parser.parse_args()
    
    if args.list_effects:
        print("\nAvailable WLED Effects:")
        print("-" * 40)
        for name, effect in WLED_EFFECTS.items():
            print(f"  {name:20} (ID: {effect.id:3}) - {effect.name}")
        print()
        return
    
    # Create controller
    controller = create_led_controller(args.type, host=args.host)
    
    if args.effect:
        if isinstance(controller, WLEDController):
            controller.preview_effect(args.effect)
            input("Press Enter to continue...")
        else:
            print("Effect preview only works with WLED controller")
        return
    
    if args.demo:
        print("\n🔮 Running Crystal Ball LED Demo\n")
        
        print("State: IDLE (waiting for seeker)")
        controller.idle()
        time.sleep(3)
        
        print("State: LISTENING (someone approaches)")
        controller.listening()
        time.sleep(3)
        
        print("State: THINKING (consulting the spirits)")
        controller.thinking()
        time.sleep(3)
        
        print("State: DRAMATIC REVEAL!")
        controller.dramatic_reveal()
        time.sleep(0.5)
        
        print("State: SPEAKING (delivering the fortune)")
        # dramatic_reveal transitions to speaking
        time.sleep(4)
        
        print("State: GOODBYE (seeker departs)")
        controller.goodbye()
        
        print("\n✨ Demo complete!\n")
        return
    
    # Interactive mode
    print("\n" + "=" * 50)
    print("LED Controller Test Mode")
    print("=" * 50)
    print("\nCommands:")
    print("  i = idle")
    print("  l = listening")
    print("  t = thinking")
    print("  s = speaking")
    print("  d = dramatic reveal")
    print("  g = goodbye")
    print("  e <name> = preview effect (WLED only)")
    print("  q = quit")
    print()
    
    while True:
        cmd = input("Command: ").strip().lower()
        
        if cmd == 'q':
            break
        elif cmd == 'i':
            controller.idle()
        elif cmd == 'l':
            controller.listening()
        elif cmd == 't':
            controller.thinking()
        elif cmd == 's':
            controller.speaking()
        elif cmd == 'd':
            controller.dramatic_reveal()
        elif cmd == 'g':
            controller.goodbye()
            break
        elif cmd.startswith('e ') and isinstance(controller, WLEDController):
            controller.preview_effect(cmd[2:])
        else:
            print("Unknown command")
    
    print("\nGoodbye!")


if __name__ == "__main__":
    main()
