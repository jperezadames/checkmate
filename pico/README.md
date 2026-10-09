# Pico LED firmware

Owner: Hsin-Chen. Contract: `contracts/interfaces.md` section 4 (serial protocol 4.3, roles and colors 4.2).

- `main.py`: MicroPython firmware. Reads one JSON command per line from USB serial, answers each with one line, drives the WS2812 matrix.
- Upload with `mpremote` (stop the backend first; both can't hold the serial port at the same time).
