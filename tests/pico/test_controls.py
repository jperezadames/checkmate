from pico import main as fw


class Value:
    def __init__(self, value):
        self.current = value
    def value(self):
        return self.current
    def read_u16(self):
        return self.current


def test_button_debounce_held_button_and_release_between_usb_polls():
    button = Value(0)
    controls = fw.Controls(Value(32768), button)
    button.current = 1
    controls.tick(1)
    button.current = 0
    controls.tick(5)
    button.current = 1
    controls.tick(9)
    controls.tick(38)
    assert controls.snapshot()['presses'] == 0
    controls.tick(39)
    controls.tick(1000)
    assert controls.snapshot()['presses'] == 1
    button.current = 0
    controls.tick(1010)
    controls.tick(1040)
    assert controls.snapshot()['presses'] == 1
    button.current = 1
    controls.tick(1050)
    controls.tick(1080)
    assert controls.snapshot()['presses'] == 2


def test_holding_button_at_boot_does_not_activate_select():
    controls = fw.Controls(Value(0), Value(1))
    controls.tick(100)
    assert controls.snapshot() == {'adc': 0, 'presses': 0}


def test_analog_smoothing_stops_and_optional_direction_reversal(monkeypatch):
    adc = Value(0)
    controls = fw.Controls(adc, Value(0))
    adc.current = 65535
    controls.tick(10)
    assert 0 < controls.snapshot()['adc'] < 65535
    for now in range(20, 1000, 10):
        controls.tick(now)
    assert controls.snapshot()['adc'] > 65000
    monkeypatch.setattr(fw, 'ROTARY_REVERSED', True)
    assert controls.snapshot()['adc'] < 535


def test_inputs_poll_is_idempotent_and_does_not_redraw_leds():
    class Strip(list):
        def write(self):
            pass
    controls = fw.Controls(Value(40000), Value(0))
    controls.presses = 7
    leds = fw.Leds(Strip([(0, 0, 0)] * 256), controls)
    first = leds.handle({'id': 10, 'cmd': 'inputs'})
    assert first == leds.handle({'id': 10, 'cmd': 'inputs'})
    assert first == {'id': 10, 'ok': True, 'adc': 40000, 'presses': 7}


def test_configuration_preserves_layout_and_enforces_firmware_brightness_cap():
    class Strip(list):
        def write(self):
            pass
    leds = fw.Leds(Strip([(0, 0, 0)] * 256))
    assert leds.handle({'cmd': 'configure', 'rotation': 90, 'mirror': True,
                        'max_brightness': 100})['ok']
    leds.handle({'cmd': 'brightness', 'value': 100})
    leds.handle({'cmd': 'set', 'squares': [{'sq': 'a1', 'role': 'engine_from'}]})
    indices = leds.layout.indices('a1')
    assert all(leds.strip[i] == (0, 0, 127) for i in indices)
    assert not leds.handle({'cmd': 'configure', 'rotation': 45})['ok']
