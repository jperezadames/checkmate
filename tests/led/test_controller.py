"""LedController against an in-memory Pico that follows the serial protocol (section 4.3)."""

import json
import time

import pytest

from checkmate.config import load_config
from checkmate.led import LedController
from checkmate.led import controller as led_controller

EXAMPLE = [{"sq": "e7", "role": "engine_from"}, {"sq": "e5", "role": "engine_to"}]


class FakePico:
    """A serial port with pico/main.py behind it."""

    def __init__(self):
        self.received = []    # commands, decoded
        self.out = []         # reply lines not read yet
        self.ignore = 0       # don't answer this many commands
        self.reject = None    # (error, message) for the next command
        self.unplugged = False
        self.closed = False
        self.adc = 32768
        self.presses = 0

    def write(self, data):
        if self.unplugged:
            raise OSError("device disconnected")
        for line in data.split(b"\n"):
            if line:
                self._answer(json.loads(line))
        return len(data)

    def _answer(self, cmd):
        self.received.append(cmd)
        if self.ignore:
            self.ignore -= 1
            return
        reply = {"id": cmd["id"], "ok": True}
        if self.reject:
            reply = {"id": cmd["id"], "ok": False, "error": self.reject[0], "message": self.reject[1]}
            self.reject = None
        elif cmd["cmd"] == "ping":
            reply["fw"] = "checkmate-pico 2.0"
        elif cmd["cmd"] == "inputs":
            reply.update(adc=self.adc, presses=self.presses)
        self.out.append(json.dumps(reply).encode() + b"\n")

    def readline(self):
        if self.unplugged:
            raise OSError("device disconnected")
        if self.out:
            return self.out.pop(0)
        time.sleep(0.002)
        return b""

    def reset_input_buffer(self):
        self.out.clear()

    def close(self):
        self.closed = True

    def last(self, cmd):
        return [c for c in self.received if c["cmd"] == cmd][-1]


@pytest.fixture
def usb(monkeypatch):
    """The USB port: usb.pico is what plugging in a Pico would open (None = nothing plugged in)."""
    class Usb:
        pico = FakePico()
        opened = []

    def open_port(port):
        if Usb.pico is None:
            raise OSError("no such device")
        Usb.opened.append(Usb.pico)
        return Usb.pico

    monkeypatch.setattr(led_controller, "find_port", lambda pattern: "/dev/ttyACM0")
    monkeypatch.setattr(led_controller, "_open_port", open_port)
    monkeypatch.setattr(led_controller, "PING_INTERVAL_S", 0.02)
    return Usb


@pytest.fixture
def make_led():
    leds = []

    def make(**config):
        leds.append(LedController({"reply_timeout_s": 0.05, "brightness": 40, **config}))
        return leds[-1]

    yield make
    for led in leds:
        led.close()


@pytest.fixture
def led(usb, make_led):
    led = make_led()
    assert led.start() == {"ok": True, "fw": "checkmate-pico 2.0"}
    return led


def wait_for(condition, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


# -- config ----------------------------------------------------------------------------------

def test_repo_config_is_valid():
    LedController(load_config()["led"])  # must not raise


@pytest.mark.parametrize("brightness", [101, -1, 0.4, "40", True])
def test_bad_brightness_in_config_raises(brightness):
    with pytest.raises(ValueError):
        LedController({"brightness": brightness})


def test_find_port_globs_then_falls_back(tmp_path, monkeypatch):
    (tmp_path / "usb-MicroPython_Board_in_FS_mode_e6614c-if00").touch()
    assert led_controller.find_port(str(tmp_path / "usb-MicroPython_*-if00")).endswith("e6614c-if00")
    monkeypatch.setattr(led_controller, "FALLBACK_PORT", str(tmp_path / "ttyACM0"))
    assert led_controller.find_port(str(tmp_path / "nothing-*")) is None
    (tmp_path / "ttyACM0").touch()
    assert led_controller.find_port(str(tmp_path / "nothing-*")) == str(tmp_path / "ttyACM0")


# -- start -----------------------------------------------------------------------------------

def test_start_pings_then_sets_brightness_and_clears(led, usb):
    assert [c["cmd"] for c in usb.pico.received] == ["ping", "configure", "brightness", "set"]
    assert usb.pico.last("brightness")["value"] == 40
    assert usb.pico.last("set")["squares"] == []
    assert led.is_connected() is True


def test_ids_start_at_1_and_count_up(led, usb):
    led.clear()
    assert [c["id"] for c in usb.pico.received] == [1, 2, 3, 4, 5]


def test_calls_before_start_are_not_started(make_led):
    led = make_led()
    assert led.show(EXAMPLE)["error"] == "NOT_STARTED"
    assert led.is_connected() is False


def test_close_twice_then_not_started(led):
    led.close()
    led.close()
    assert led.clear()["error"] == "NOT_STARTED"


# -- section 4.1 methods ---------------------------------------------------------------------

def test_show_sends_set(led, usb):
    assert led.show(EXAMPLE) == {"ok": True}
    assert usb.pico.last("set")["squares"] == EXAMPLE


@pytest.mark.parametrize("bad", [
    {"e7": "engine_from"},                                         # not a list
    [{"sq": "z9", "role": "engine_from"}],                         # bad square
    [{"sq": "e7", "role": "from"}],                                # unknown role
    [{"sq": "e7"}],                                                # no role
    [{"sq": "e7", "role": "error"}, {"sq": "e7", "role": "check"}],  # square twice
])
def test_show_bad_request_sends_nothing(led, usb, bad):
    sent = len(usb.pico.received)
    assert led.show(bad)["error"] == "BAD_REQUEST"
    assert len(usb.pico.received) == sent


def test_clear_brightness_and_test_commands(led, usb):
    assert led.clear() == {"ok": True}
    assert led.set_brightness(25) == {"ok": True}
    assert led.self_test() == {"ok": True}
    assert [c["cmd"] for c in usb.pico.received[-3:]] == ["clear", "brightness", "test"]
    assert usb.pico.last("brightness")["value"] == 25


@pytest.mark.parametrize("bad", [101, -5, 50.0, "50", None])
def test_set_brightness_bad_request(led, bad):
    assert led.set_brightness(bad)["error"] == "BAD_REQUEST"


def test_pico_error_is_led_rejected(led, usb):
    usb.pico.reject = ("BAD_ROLE", "sparkle")
    res = led.show(EXAMPLE)
    assert res["error"] == "LED_REJECTED"
    assert res["message"] == "BAD_ROLE: sparkle"
    assert led.is_connected() is True  # the Pico did answer


# -- timeouts and recovery (section 4.3) -----------------------------------------------------

def test_one_lost_reply_is_resent_with_the_same_id(led, usb):
    usb.pico.ignore = 1
    assert led.show(EXAMPLE) == {"ok": True}
    first, again = usb.pico.received[-2:]
    assert first == again


def test_no_reply_twice_disconnects_then_reconnects_and_restores(led, usb):
    usb.pico.ignore = 2
    assert led.show(EXAMPLE)["error"] == "LED_DISCONNECTED"
    assert led.is_connected() is False
    # The background thread pings again; this Pico answers, so it gets the pattern back.
    assert wait_for(led.is_connected)
    assert usb.pico.last("set")["squares"] == EXAMPLE


def test_unplugged_then_plugged_back_in(led, usb):
    usb.pico.unplugged = True
    start = time.monotonic()
    assert led.show(EXAMPLE)["error"] == "LED_DISCONNECTED"
    assert time.monotonic() - start < 1.2
    # Main keeps going; what it asks for while unplugged is shown after the Pico comes back.
    assert led.set_brightness(10)["error"] == "LED_DISCONNECTED"
    usb.pico = FakePico()
    assert wait_for(led.is_connected)
    assert usb.pico.last("brightness")["value"] == 10
    assert usb.pico.last("set")["squares"] == EXAMPLE


def test_start_without_pico_keeps_trying(usb, make_led):
    usb.pico = None
    led = make_led()
    assert led.start()["error"] == "LED_DISCONNECTED"
    usb.pico = FakePico()
    assert wait_for(led.is_connected)
    assert [c["cmd"] for c in usb.pico.received] == ["ping", "configure", "brightness", "set"]


def test_controls_share_the_led_connection_and_do_not_replay_on_reconnect(usb, make_led):
    messages = []
    led = make_led(rotation=90)
    led.set_input_callback(messages.append)
    assert led.start()["ok"]
    assert usb.pico.last("configure")["rotation"] == 90
    assert wait_for(lambda: len(messages) == 1)
    assert messages[0]["position"] == pytest.approx(32768 / 65535)
    usb.pico.adc += 20  # ADC jitter produces no navigation events.
    time.sleep(0.08)
    assert len(messages) == 1
    usb.pico.adc = 65535
    usb.pico.presses = 2
    assert wait_for(lambda: sum(m["select"] for m in messages) == 2)
    assert all(m["position"] == 1 for m in messages[1:])
    assert led.show(EXAMPLE)["ok"]
    assert len(usb.opened) == 1
    usb.pico.unplugged = True
    assert wait_for(lambda: not led.is_connected())
    usb.pico = FakePico()
    usb.pico.presses = 15  # The new session's old presses are ignored.
    assert wait_for(led.is_connected)
    assert wait_for(lambda: messages[-1]["position"] == pytest.approx(32768 / 65535))
    assert sum(m["select"] for m in messages) == 2
    assert usb.pico.last("set")["squares"] == EXAMPLE


def test_old_pico_firmware_fails_with_upload_instructions(usb, make_led):
    answer = usb.pico._answer
    def old_answer(cmd):
        answer(cmd)
        if cmd['cmd'] == 'ping':
            reply = json.loads(usb.pico.out[-1])
            reply['fw'] = 'checkmate-led 1.0'
            usb.pico.out[-1] = json.dumps(reply).encode() + b'\n'
    usb.pico._answer = old_answer
    result = make_led().start()
    assert result['error'] == 'LED_DISCONNECTED'
    assert 'Upload' in result['message']
