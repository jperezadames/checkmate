"""Between the asyncio side (routes, WebSockets) and the game loop thread (section 5.1).

The loop thread calls publish(); every WebSocket gets the messages through its own
asyncio.Queue, in order. Commands go the other way through `commands`, a queue.Queue.
"""

import asyncio
import queue
from concurrent.futures import TimeoutError as FutureTimeout

from checkmate.game import DebugImageRequest, check_command

IMAGE_TIMEOUT_S = 8.0  # the loop may be busy for a while (calibrate() takes up to 5 s)


class Hub:
    def __init__(self):
        self.commands = queue.Queue()
        self.info = None      # last `info` and `state` from the loop, for new clients and /api
        self.state = None
        self.clients = set()  # one asyncio.Queue per WebSocket
        self.loop = None      # the server's asyncio loop, while it runs

    # -- game loop thread -----------------------------------------------------------------------

    def publish(self, msg: dict):
        if msg["type"] == "info":
            self.info = msg
        elif msg["type"] == "state":
            self.state = msg
        loop = self.loop
        if loop is not None:
            try:
                loop.call_soon_threadsafe(self.send_to_all, msg)
            except RuntimeError:  # the server is shutting down
                pass

    # -- asyncio side ---------------------------------------------------------------------------

    def send_to_all(self, msg: dict):
        for out in self.clients:
            out.put_nowait(msg)

    def connect(self) -> asyncio.Queue:
        """A new WebSocket's queue, starting with the current info and state (section 5.1)."""
        out = asyncio.Queue()
        for msg in (self.info, self.state):
            if msg is not None:
                out.put_nowait(msg)
        self.clients.add(out)
        return out

    def disconnect(self, out: asyncio.Queue):
        self.clients.discard(out)

    def submit(self, cmd):
        """Check a UI command (5.4, 5.5) and queue it for the loop. None, or the error to send back."""
        phase = self.state["phase"] if self.state else "starting"
        problem = check_command(cmd, phase)
        print(f"[command] {cmd!r}" + (f" rejected: {problem['message']}" if problem else ""), flush=True)
        if problem is None:
            self.commands.put(cmd)
        return problem

    def debug_image(self):
        """JPEG bytes from camera.get_debug_image(), via the loop thread, or None. Blocks."""
        request = DebugImageRequest()
        self.commands.put(request)
        try:
            return request.reply.result(timeout=IMAGE_TIMEOUT_S)
        except FutureTimeout:
            return None
