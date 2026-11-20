"""Pico inputs reach connected screens without replaying a click on reconnection."""

import asyncio

from checkmate.server.hub import Hub


def test_new_screen_receives_angle_without_replaying_select():
    hub = Hub()
    hub.publish({"type": "input", "position": 0.7, "select": True})
    out = hub.connect()
    assert out.get_nowait() == {"type": "input", "position": 0.7, "select": False}
    assert out.empty()
    hub.disconnect(out)
    assert not hub.clients


def test_existing_screens_receive_each_press_in_order():
    async def check():
        hub = Hub()
        hub.loop = asyncio.get_running_loop()
        out = hub.connect()
        messages = [
            {"type": "input", "position": 0.2, "select": False},
            {"type": "input", "position": 0.2, "select": True},
            {"type": "input", "position": 0.8, "select": False},
        ]
        for message in messages:
            hub.publish(message)
        for message in messages:
            assert await asyncio.wait_for(out.get(), timeout=1) == message
        assert out.empty()

    asyncio.run(check())
