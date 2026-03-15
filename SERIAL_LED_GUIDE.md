# Serial LED Control Guide

Control WS2812B/NeoPixel LED strips from the Crystal Ball using an Arduino or Raspberry Pi Pico over USB serial. This is an alternative to the recommended [WLED](https://kno.wled.ge/) approach for situations where WiFi is unavailable or you want direct wired control.

## How It Works

The serial LED system is a two-part design:

```
┌──────────────┐    USB Serial    ┌────────────────────┐    Data Pin   ┌──────────────┐
│   Mini PC    │ ──────────────>  │  Arduino / Pico    │ ────────────> │  LED Strip   │
│ crystal_ball │   Single-byte    │  (runs animations) │               │  (WS2812B)   │
│    .py       │   commands       │                    │               │              │
└──────────────┘                  └────────────────────┘               └──────────────┘
```

1. The Python app sends a **single ASCII character** over USB serial whenever the crystal ball changes state
2. The microcontroller receives that character and switches to the corresponding LED animation
3. All animation logic runs on the microcontroller — the Python side is intentionally minimal

## Serial Protocol

| Character | State            | Suggested Effect                        |
|-----------|------------------|-----------------------------------------|
| `R`       | Sleeping         | Very dim, slow purple breathe           |
| `I`       | Idle             | Gentle purple pulse                     |
| `L`       | Listening        | Brighter cyan-green fairy twinkle       |
| `T`       | Thinking         | Blue swirling/flowing                   |
| `S`       | Speaking         | Warm orange candle flicker              |
| `D`       | Dramatic reveal  | Bright white flash, then settle         |
| `G`       | Goodbye          | Slow fade to darkness                   |
| `O`       | Off              | All LEDs off                            |

Default serial settings: **9600 baud**, 8N1. Port defaults to `/dev/ttyUSB0` on Linux, but can be any serial port.

## Hardware You Need

- **Microcontroller:** Arduino Nano, Arduino Uno, or Raspberry Pi Pico (any board with USB serial and a 5V-tolerant data pin)
- **LED strip:** WS2812B (NeoPixel) — any length, though 30-60 LEDs works well for a crystal ball prop
- **Power supply:** 5V, sized for your strip (budget ~60mA per LED at full white brightness)
- **Wiring:**
  - Microcontroller data pin (e.g. pin 6) to LED strip data-in
  - Shared ground between microcontroller and LED strip power supply
  - USB cable from microcontroller to the mini PC

### Wiring Diagram

```
USB from Mini PC
       │
  ┌────┴────┐
  │ Arduino │
  │  Nano   │──── Pin 6 ──────> DIN (LED Strip Data In)
  │         │
  │     GND │──┐
  └─────────┘  │
               ├──── GND (LED Strip)
  ┌────────┐   │
  │  5V    │───┘
  │ Power  │──────── +5V (LED Strip)
  │ Supply │
  └────────┘
```

> **Tip:** For strips longer than ~30 LEDs, power the strip directly from the 5V supply rather than through the Arduino's 5V pin. Always connect grounds together.

## Microcontroller Firmware

You need to write (or flash) firmware on the microcontroller that reads serial commands and runs LED animations. Below is a complete Arduino example using the FastLED library.

### Arduino Example

Install the **FastLED** library in the Arduino IDE (Sketch > Include Library > Manage Libraries > search "FastLED").

```cpp
#include <FastLED.h>

#define LED_PIN     6
#define NUM_LEDS    30
#define BRIGHTNESS  150

CRGB leds[NUM_LEDS];

char currentMode = 'R';  // Start in sleeping mode

void setup() {
  Serial.begin(9600);
  FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.clear();
  FastLED.show();
}

void loop() {
  // Check for new command
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'R' || cmd == 'I' || cmd == 'L' || cmd == 'T' ||
        cmd == 'S' || cmd == 'D' || cmd == 'G' || cmd == 'O') {
      currentMode = cmd;
    }
  }

  // Run the current animation frame
  switch (currentMode) {
    case 'R': animSleeping();       break;
    case 'I': animIdle();           break;
    case 'L': animListening();      break;
    case 'T': animThinking();       break;
    case 'S': animSpeaking();       break;
    case 'D': animDramaticReveal(); break;
    case 'G': animGoodbye();        break;
    case 'O': animOff();            break;
  }

  FastLED.show();
  delay(20);  // ~50 FPS
}

// --- Animation Functions ---
// Each runs one frame per loop() call. Use millis() for timing,
// NOT delay(), so the loop stays responsive to serial commands.

void animSleeping() {
  // Very dim slow purple breathe
  uint8_t val = beatsin8(10, 5, 30);  // 10 BPM, range 5-30
  fill_solid(leds, NUM_LEDS, CHSV(192, 255, val));  // Purple
}

void animIdle() {
  // Gentle purple pulse
  uint8_t val = beatsin8(20, 40, 120);
  fill_solid(leds, NUM_LEDS, CHSV(192, 255, val));
}

void animListening() {
  // Brighter cyan-green with twinkling
  fill_solid(leds, NUM_LEDS, CHSV(96, 255, 150));  // Cyan-green base
  // Random twinkle
  if (random8() < 80) {
    leds[random16(NUM_LEDS)] = CHSV(96, 200, 255);
  }
  fadeToBlackBy(leds, NUM_LEDS, 20);
}

void animThinking() {
  // Blue swirl using a moving dot pattern
  fadeToBlackBy(leds, NUM_LEDS, 30);
  uint16_t pos = beatsin16(15, 0, NUM_LEDS - 1);
  leds[pos] = CHSV(160, 255, 220);  // Blue
}

void animSpeaking() {
  // Warm orange candle flicker
  for (int i = 0; i < NUM_LEDS; i++) {
    uint8_t flicker = random8(180, 255);
    leds[i] = CHSV(24, 255, flicker);  // Warm orange
  }
}

void animDramaticReveal() {
  // Bright white flash then transition to speaking
  static unsigned long flashStart = 0;
  if (flashStart == 0) {
    flashStart = millis();
    fill_solid(leds, NUM_LEDS, CRGB::White);
    FastLED.setBrightness(255);
  } else if (millis() - flashStart > 300) {
    // Flash done, switch to speaking
    FastLED.setBrightness(BRIGHTNESS);
    flashStart = 0;
    currentMode = 'S';
  }
}

void animGoodbye() {
  // Slow fade to darkness
  fadeToBlackBy(leds, NUM_LEDS, 3);
}

void animOff() {
  FastLED.clear();
}
```

### Raspberry Pi Pico (CircuitPython) Example

Install CircuitPython on your Pico and add the `neopixel` library from the Adafruit CircuitPython Bundle.

```python
import board
import neopixel
import time
import random
import math
import supervisor

NUM_LEDS = 30
pixels = neopixel.NeoPixel(board.GP0, NUM_LEDS, auto_write=False)
pixels.brightness = 0.6

mode = 'R'

def breathe(hue_r, hue_g, hue_b, speed=1.0, low=5, high=150):
    """Pulsing brightness on a solid color."""
    t = time.monotonic() * speed
    val = low + (high - low) * (0.5 + 0.5 * math.sin(t))
    scale = val / 255.0
    pixels.fill((int(hue_r * scale), int(hue_g * scale), int(hue_b * scale)))

while True:
    # Check for serial command
    if supervisor.runtime.serial_bytes_available:
        cmd = input().strip()
        if cmd in ('R', 'I', 'L', 'T', 'S', 'D', 'G', 'O'):
            mode = cmd

    if mode == 'R':
        breathe(128, 0, 255, speed=0.5, low=2, high=30)
    elif mode == 'I':
        breathe(128, 0, 255, speed=1.0, low=20, high=120)
    elif mode == 'L':
        pixels.fill((0, 200, 100))
        i = random.randint(0, NUM_LEDS - 1)
        pixels[i] = (0, 255, 180)
    elif mode == 'T':
        pos = int((NUM_LEDS - 1) * (0.5 + 0.5 * math.sin(time.monotonic() * 2)))
        pixels.fill((0, 0, 0))
        pixels[pos] = (0, 80, 255)
    elif mode == 'S':
        for i in range(NUM_LEDS):
            v = random.randint(180, 255)
            pixels[i] = (v, int(v * 0.4), 0)
    elif mode == 'D':
        pixels.fill((255, 255, 255))
        pixels.show()
        time.sleep(0.3)
        mode = 'S'
    elif mode == 'G':
        for i in range(NUM_LEDS):
            r, g, b = pixels[i]
            pixels[i] = (max(0, r - 2), max(0, g - 2), max(0, b - 2))
    elif mode == 'O':
        pixels.fill((0, 0, 0))

    pixels.show()
    time.sleep(0.02)
```

## Running the Crystal Ball with Serial LEDs

### 1. Flash the firmware

Upload the Arduino sketch or CircuitPython script to your microcontroller.

### 2. Find your serial port

**Linux:**
```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

**Windows (PowerShell):**
```powershell
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description
```

**macOS:**
```bash
ls /dev/tty.usb*
```

### 3. Install pyserial

```bash
pip install pyserial
```

### 4. Test the connection

You can test the serial protocol directly before running the full crystal ball:

```bash
# Quick test — send the idle command
python -c "import serial, time; s = serial.Serial('/dev/ttyUSB0', 9600); time.sleep(2); s.write(b'I')"

# Interactive test using the built-in LED test CLI
python led_integration.py --type serial
```

### 5. Launch the crystal ball

**Linux / macOS:**
```bash
./run.sh --led-type serial
```

**Windows (PowerShell):**
```powershell
venv\Scripts\python crystal_ball.py --led-type serial
```

The auto-detect mode (`--led-type auto`) will also find serial controllers if WLED is not available. It probes `/dev/ttyUSB0`, `/dev/ttyACM0`, `COM3`, and `COM4` in order.

## Customizing the Serial Port

The default port is `/dev/ttyUSB0` at 9600 baud. To use a different port, you'll need to modify the `SerialLEDController` call in `led_integration.py` or pass it through the factory function:

```python
# In led_integration.py, the serial controller accepts:
SerialLEDController(port='/dev/ttyACM0', baud=9600)
```

## Troubleshooting

| Problem                                  | Fix                                                                                                                                                     |
|------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| `Permission denied: '/dev/ttyUSB0'`      | Add your user to the `dialout` group: `sudo usermod -aG dialout $USER` then log out/in                                                                  |
| LEDs don't respond after connecting      | The Arduino resets on serial connect — the 2-second delay in the Python code accounts for this. If animations still don't start, increase the delay     |
| `pyserial not installed`                 | Run `pip install pyserial` in your venv                                                                                                                 |
| Wrong colors or flickering               | Check your strip's color order (GRB vs RGB) in the firmware — WS2812B is typically GRB                                                                  |
| LEDs work in test but not in crystal ball| Make sure no other program (Arduino Serial Monitor, etc.) has the port open                                                                             |
| Port not found on Windows                | Check Device Manager for the COM port number; Arduino clones may need a CH340 driver                                                                    |

## Serial vs WLED: When to Use Which

|                | Serial                                                     | WLED                                     |
|----------------|------------------------------------------------------------|------------------------------------------|
| **Setup**      | Write/flash firmware yourself                              | Flash WLED, configure via web UI         |
| **Connection** | USB cable (reliable, no network)                           | WiFi (can drop, needs network)           |
| **Effects**    | You implement them                                         | 100+ built-in effects                    |
| **Tweaking**   | Re-flash firmware to change                                | Adjust via web UI or API in real time    |
| **Latency**    | Very low (~ms)                                             | Low (~10-50ms over WiFi)                 |
| **Best for**   | No WiFi available, want full control, learning electronics | Quick setup, rich effects, easy tuning   |

