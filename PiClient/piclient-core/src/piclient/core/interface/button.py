# pyright: reportPrivateImportUsage=false
from types import TracebackType

import asyncio
from datetime import timedelta

import gpiod
from gpiod.line import Direction, Edge
from loguru import logger

from ..lib import export

@export
class AsyncButton:
    """
    Asynchronous button handler using gpiod.

    To wait for a button press or release, use the `pressed` and `released` asyncio events.
    """

    _instance_counter = 0

    def __init__(self, chip_name: str, *button_pins: int, debounce: int = 20):
        """
        Initialize the AsyncButton.

        :param chip_name: The name of the GPIO chip.
        :param button_pins: The GPIO pin numbers for the buttons.
        """
        AsyncButton._instance_counter += 1

        self.chip = gpiod.Chip(chip_name)
        self.line_offsets: tuple[int, ...] = button_pins
        self.request: gpiod.LineRequest | None = None 
        self.debounce = debounce

        self.pressed = asyncio.Event()
        self.released = asyncio.Event()

        self._id = AsyncButton._instance_counter
        self._loop: asyncio.AbstractEventLoop | None = None
        self._background_task = None

    async def __aenter__(self):
        self._loop = asyncio.get_running_loop()
        self._background_task = self._loop.run_in_executor(None, self._background_listener)
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        if self.request is not None:
            self.request.release()
        if self._background_task is not None:
            try:
                await asyncio.wait_for(self._background_task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                logger.warning(f"Zombie background task for button-listener-{self._id} will need manual cleanup.")

        self.chip.close()

    def _background_listener(self) -> None:
        """
        Background listener for the button events.

        This method runs in a separate thread and listens for button press and release events.
        When an event is detected, it sets the corresponding asyncio event (pressed or released).
        """
        if self._loop is None:
            raise RuntimeError("AsyncButton must be used within an async context manager.")
        try:
            with self.chip.request_lines(
                consumer=f"button-listener-{self._id}",
                config={
                    # Disgusting API gpiod, force me to use single element tuple instead of passing the whole tuple of offsets.
                    (offset,): gpiod.LineSettings( 
                        direction=Direction.INPUT,
                        edge_detection=Edge.BOTH,
                        bias=gpiod.line.Bias.PULL_UP,
                        debounce_period=timedelta(milliseconds=self.debounce)
                    )
                    for offset in self.line_offsets
                },
            ) as self.request:

                while True:
                    if self.request.wait_edge_events(timeout=timedelta(seconds=1)):
                        for event in self.request.read_edge_events():
                            if event.event_type == gpiod.EdgeEvent.Type.FALLING_EDGE:
                                self._loop.call_soon_threadsafe(self.pressed.set)
                            elif event.event_type == gpiod.EdgeEvent.Type.RISING_EDGE:
                                self._loop.call_soon_threadsafe(self.released.set)
        except (EOFError, OSError, gpiod.ChipClosedError, asyncio.CancelledError, gpiod.exception.RequestReleasedError):
            pass
    