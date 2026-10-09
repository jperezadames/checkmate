"""Game loop (contracts/interfaces.md section 6).

Runs in one background thread inside the FastAPI backend at about 10 Hz. It is the only
thread that calls Camera, GameEngine and LedController. UI commands arrive through a
queue.Queue; after any change it builds a new `state` (section 5.3) and broadcasts it.

Not implemented yet: waiting for the engine (Joel) and LED (Hsin-Chen) modules.
"""


def run_game_loop(camera, engine, led, commands, broadcast, stop_event):
    """TODO: phases idle -> setup_check -> human_turn / engine_thinking -> ... (section 6)."""
    raise NotImplementedError
