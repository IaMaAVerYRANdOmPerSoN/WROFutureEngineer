"""
Drive command executor for the PiClient.
This module provides a fully-async, single-consumer executor for drive commands.
It is latest-wins without blocking or contention, and is designed to be used with the `Client` class for controlling the robot's drive motors.
"""

from typing import Any, NoReturn, Self

import asyncio

from loguru import logger
from ...lib import export
from .client import Client


@export
class DriveCommandExecutor:
    """
    A fully-async, single-consumer executor for drive commands.

    The control loop calls `submit()` (non-blocking) with the latest desired
    drive command; a dedicated background coroutine `await`s each command to
    completion sequentially. This guarantees execution without ever blocking
    the producer, and without `asyncio.create_task` fire-and-forget (which can
    be garbage collected before it runs, or pile up faster than the serial
    link drains).

    Commands coalesce latest-wins: if newer commands arrive while one is in
    flight, only the freshest is kept, so the robot always acts on the most
    recent steering target instead of replaying a stale backlog. It's a single
    long-lived task on the event loop -> no threads, no pools, no GIL contention.
    """

    def __init__(self, client: Client) -> None:
        """
        :param client: The `Client` whose `drive_motors` the worker will call.
        """
        self._client: Client = client
        self._pending: tuple[float, float, float] | None = None
        self._wakeup = asyncio.Event()
        self._worker_task: asyncio.Task[NoReturn] | None = None
        self.latest_command: tuple[float, float, float] = (0.0, 90.0, 0.0)
        self.command_submitted: bool = False

    async def __aenter__(self) -> Self:
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Drive command executor started")
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Drive command executor stopped")

    async def reload(self) -> Self:
        """Hot reload after changing attributes.

        Tears down existing hardware resources, reinitialises the worker
        with the updated configuration, and cleans up on failure before
        re-raising.

        ALWAYS call after changing attributes to reload internal context.
        Not doing so will lead to unpredictable behaviour.

        :returns: ``self``
        :raises Exception: Re-raises any exception during reload
        """
        await self.__aexit__()
        try:
            return await self.__aenter__()
        except Exception:
            await self.__aexit__()
            raise

    def submit(self, speed: float, angle: float, duration: float) -> None:
        """
        Hand the worker the latest drive command. Non-blocking; latest-wins.

        :param speed: Normalized motor speed in [-1, 1] (see `Client.set_motor_speed`).
        :param angle: Servo angle in degrees.
        :param duration: Motor run duration in seconds.
        """
        self.latest_command = (speed, angle, duration)
        self.command_submitted = True
        self._pending = self.latest_command
        self._wakeup.set()

    async def _worker(self) -> NoReturn:
        """Background coroutine that consumes drive commands sequentially.

        Waits on :attr:`_wakeup`, pops the latest pending command, and
        awaits :meth:`Client.drive_motors`. Runs until cancelled.
        """
        while True:
            await self._wakeup.wait()
            self._wakeup.clear()

            command: tuple[float, float, float] | None = self._pending
            self._pending = None
            if command is None:
                continue

            try:
                speed, angle, duration = command
                await self._client.drive_motors(speed, int(angle), duration)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Drive command {command} failed: {e}")
