# Pico LED firmware

Owner: Hsin-Chen. Contract: `contracts/interfaces.md` section 4 (serial protocol 4.3, roles and colors 4.2).

- `main.py`: MicroPython firmware. Reads one JSON command per line from USB serial (`ping`, `set`, `clear`, `brightness`, `test`), answers each with one line, and drives the WS2812 matrix. The colors of the roles live here (`ROLE_COLORS`); `error` blinks at 2 Hz.
- Hardware settings at the top of `main.py`: `DATA_PIN`, `SERPENTINE`, `ROTATION`, `MIRROR`, and `MAX_BRIGHTNESS` (a hard cap, whatever the Pi asks for).
- Upload with `mpremote cp pico/main.py :main.py`, then reset the Pico (stop the backend first; both can't hold the serial port at the same time). On boot the 4 corner squares light for 1 s.
- Check the orientation with the `test` command (`LedController.self_test()`): a1 red, h1 green, h8 blue, a8 white, one after another. If they are in the wrong corners, change `ROTATION` / `MIRROR`.
- Tests run on a computer without a Pico: `pytest tests/pico`.
