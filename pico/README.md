# Pico LED and Grove controls

The Seeed Grove Shield uses A0 (GP26/ADC0) for the bounded Grove Rotary Angle Sensor, D20 (GP20) for the active-high Grove Button, and D16 (GP16) for the 16×16 WS2812 matrix data. Set the shield's Grove power switch to **3.3 V** for the analog input. Use the matrix's external 5 V supply and a shared ground, with appropriate data level shifting. The complete wiring and migration instructions are in [pi-setup.txt](../pi-setup.txt).

Install MicroPython for the Pico model. Stop the CheckMate backend and close Thonny, then run from the repo root on the Pi:

```bash
.venv/bin/pip install mpremote
.venv/bin/mpremote connect auto fs cp checkmate/led/matrix.py :matrix.py
.venv/bin/mpremote connect auto fs cp pico/main.py :main.py
.venv/bin/mpremote connect auto reset
```

Both files are required. `matrix.py` is shared with the host tests and defines role colours and square-to-LED geometry. Configured layout and brightness are restored each time the Pi connects. Use `LedController.self_test()` to light a1 red, h1 green, h8 blue, and a8 white in order.

Firmware identity is `checkmate-pico 2.0`. USB uses one JSON command/reply per line with matching `id`. The Pi is the only serial owner. Commands are `ping`, `configure`, `set`, `clear`, `brightness`, `test`, and `inputs`. Replies to `inputs` include `adc` (0–65535) and a wrapping `presses` counter. Retrying that poll keeps the same press count until another debounced press. The host seeds the counter on reconnection so old presses do not activate a new screen.

`main.py` samples controls continuously while receiving LED commands. D20 uses 30 ms debounce, counts one press while held, and retains presses after release until the Pi polls. Angle readings use a low-pass filter. Change `ROTARY_REVERSED` if clockwise runs backwards, or `BUTTON_ACTIVE` for a different switch module. The browser maps the angle across the current screen's enabled controls, with hysteresis at boundaries.

To inspect control input, stop the backend and run this diagnostic from the repo root. Move the knob and press/release Select during the five-second window. You should see changing `position` values and a `select: True` event for each press.

```bash
.venv/bin/python - <<'PY'
import time
from checkmate.config import load_config
from checkmate.led import LedController
controller = LedController(load_config()["led"])
controller.set_input_callback(print)
try:
    print(controller.start())
    time.sleep(5)
finally:
    controller.close()
PY
```

This prints normalized `position` and `select` events. Run `pytest tests/pico tests/led tests/server` for firmware/USB tests without hardware.

Hardware references are [Seeed's Pico shield examples](https://wiki.seeedstudio.com/Grove-Starter-Kit-for-Raspberry-Pi-Pico/), [Grove Button polarity](https://wiki.seeedstudio.com/Grove-Button/), and [MicroPython RP2 ADC](https://docs.micropython.org/en/latest/rp2/quickref.html#adc-analog-to-digital-conversion).
