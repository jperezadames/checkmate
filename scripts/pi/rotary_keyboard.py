"""Translate the Raspberry Pi's rotary-encoder events into arrow key taps."""

from contextlib import closing
from pathlib import Path

from evdev import InputDevice, UInput, ecodes


def find_encoder() -> Path:
    # Match the kernel driver so a mouse or a changed event number cannot
    # redirect the bridge to another input device.
    devices = [
        Path('/dev/input') / event.name
        for event in Path('/sys/class/input').glob('event*')
        if (event / 'device/device/driver').resolve().name == 'rotary-encoder'
    ]
    if len(devices) != 1:
        raise SystemExit(
            f'Expected one GPIO rotary encoder, found {len(devices)}. '
            'Check the rotary-encoder overlay in /boot/firmware/config.txt.'
        )
    return devices[0]


def main() -> None:
    with closing(InputDevice(str(find_encoder()))) as encoder:
        axes = encoder.capabilities().get(ecodes.EV_REL, [])
        if ecodes.REL_X not in axes:
            raise SystemExit('Set relative_axis on the rotary-encoder overlay.')

        keys = {ecodes.EV_KEY: [ecodes.KEY_LEFT, ecodes.KEY_RIGHT]}
        with UInput(keys, name='CheckMate Rotary') as keyboard:
            print(f'Reading {encoder.path} as CheckMate Rotary', flush=True)
            for event in encoder.read_loop():
                if event.type != ecodes.EV_REL or event.code != ecodes.REL_X or not event.value:
                    continue
                key = ecodes.KEY_RIGHT if event.value > 0 else ecodes.KEY_LEFT
                for _ in range(abs(event.value)):
                    keyboard.write(ecodes.EV_KEY, key, 1)
                    keyboard.syn()
                    keyboard.write(ecodes.EV_KEY, key, 0)
                    keyboard.syn()


if __name__ == '__main__':
    main()
