"""Serial communication protocol client.

Provides :class:`Client` for request/response communication with the
Arduino over async serial, and :class:`DriveCommandExecutor` for
coalescing drive commands with latest-wins semantics.
"""

from _asyncio import Future, Task

import aioserial
import asyncio
import re
from loguru import logger
from itertools import cycle
from collections.abc import Coroutine
from typing import Any, Literal, NoReturn, Self
from ..lib import GLOBAL_CONFIG, export
from collections import defaultdict


@export
class Client:
    """Async serial client for the Arduino communication protocol.

    Manages a TID-based request/response pipeline with a background
    serial listener. Supports motor, servo, LED, and ping commands.

    :ivar _serial: Underlying :class:`aioserial.AioSerial` instance.
    :ivar port: Serial port path.
    :ivar baud: Serial baud rate.
    :ivar timeout: Default timeout for granular requests.
    :ivar TIDS: Cyclic transaction ID generator.
    :ivar is_connected: Whether the Arduino handshake has succeeded.
    """

    def __init__(
            self,
            port: str = GLOBAL_CONFIG().ClientConfig.SERIAL_PORT,
            baud: int = GLOBAL_CONFIG().ClientConfig.SERIAL_BAUD,
            timeout: float = GLOBAL_CONFIG().ClientConfig.SERIAL_TIMEOUT,
            retries: int = GLOBAL_CONFIG().ClientConfig.CONNECT_RETRIES,
            max_speed: int = GLOBAL_CONFIG().ClientConfig.MAX_SPEED,
            tid_start: int = GLOBAL_CONFIG().ClientConfig.TID_START,
            tid_end: int = GLOBAL_CONFIG().ClientConfig.TID_END,
            wait_re_pattern: str = GLOBAL_CONFIG().ClientConfig.WAIT_RE_PATTERN,
            loop: asyncio.AbstractEventLoop | None = None,
    ):
        """
        The constructor for the `Client` class

        :param self: The instance of Client
        :param port: The serial port passed to `aioserial.AioSerial`.
        :param baud: The baudrate of the serial protocol.
        :param timeout: Default timeout for granular requests.
        :param tid_start: First transaction ID (inclusive).
        :param tid_end: Last transaction ID (inclusive) before cycling.
        :param wait_re_pattern: Regex pattern for Arduino WAITMS responses.

        :returns self: an instance of `Client`
        """

        self._serial = None
        self.port, self.baud = port, baud
        self.timeout: float = timeout
        self.retries: int = retries
        self._tids: cycle[int] = cycle(
            [i for i in range(tid_start, tid_end + 1)])
        self.max_speed: int = max_speed
        self._wait_re: re.Pattern[str] = re.compile(wait_re_pattern)
        self.is_connected = False

        try:
            self.loop: asyncio.AbstractEventLoop = loop if loop else asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "No event loop currently running in thread, are you building docs?")

        self._pending_requests: defaultdict[str, asyncio.Future[tuple[str, str]]] = defaultdict(
            asyncio.Future)  # {TID: future} -> {TID: response}
        self._lock = asyncio.Lock()
        self._drive_semaphore = asyncio.BoundedSemaphore(1)
        self.servo_angle = 0

        logger.info(
            f"======= CLIENT INSTANCE STARTED: Port = {self.port}, Baud = {self.baud}, Timeout = {self.timeout} ======= ")

    async def _serial_listener(self) -> NoReturn:
        """Background task that reads lines from serial and resolves pending futures.

        Each incoming line is parsed for a transaction ID (TID); if a pending
        future exists for that TID, the line is delivered as its result.

        :param self: The instance of :class:`Client`.
        :returns: This coroutine runs indefinitely and never returns normally.
        :raises AssertionError: If the serial interface is not initialized.
        """
        assert self._serial is not None, "Serial interface not initialized. Did you forget to use the async context manager?"

        while True:
            line: bytes = await self._serial.readline_async()
            response: str = line.decode('utf-8').strip()

            logger.debug(f"Line read from serial buffer: '{response}'")

            parts: list[str] = response.split(" ", 1)
            if len(parts) < 2:
                continue

            tid, message = parts[0], parts[1]

            if tid in self._pending_requests:
                future: Future[tuple[str, str]] = self._pending_requests[tid]
                if not future.done():
                    future.set_result((tid, message))

    async def __aenter__(self) -> Self:
        """
        Async context manager entry point that initializes the serial interface
        and starts the background serial listener task.

        :param self: The instance of `Client`
        :return: The current `Client` instance.
        :rtype: Client
        """
        self._serial = aioserial.AioSerial(
            self.port, self.baud, timeout=self.timeout)

        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda loop, context: None)

        if not hasattr(self, "_listener_task"):
            self._listener_task: Task[NoReturn] = asyncio.create_task(
                self._serial_listener())
            logger.info("Serial Listener Started")
        else:
            logger.warning("Serial listener already started in this context")
        return self

    async def __aexit__(self, *args: Any) -> None:
        """
        Async context manager exit point that cancels the background serial
        listener task and closes the serial connection.

        :param self: The instance of `Client`
        :param args: Exception type, value, and traceback (per context manager protocol).
        """
        if hasattr(self, "_listener_task"):
            self._listener_task.cancel()
            self._serial.close() if self._serial else None
            logger.info("Serial listener terminated without errors")
        else:
            logger.warning("No serial listener to cancel")

    async def reload(self) -> Self:
        """Hot reload after changing attributes.

        Tears down existing hardware resources, reinitialises the client
        with the updated configuration, and cleans up on failure before
        re-raising

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

    async def _request(
        self,
        command: str,
        timeout: float | None = None
    ) -> str:
        """Send a request to the Arduino and await its response.

        Assigns a unique transaction ID, writes the command to serial,
        and waits for the matching TID response. Handles ``WAITMS``
        responses by re-registering the future with an extended timeout.

        :param command: The command string to send (e.g. ``"SET_MOTOR 50 0.5"``).
        :param type: The command type string (used only for logging).
        :param timeout: Maximum time in seconds to wait for a response.
        :returns: The response string from the Arduino, or an error string.
        :raises AttributeError: If the serial interface is not initialized.
        """
        if not self._serial:
            raise AttributeError(
                "Please Use the Client's aysnc context manager to initilize hardware resources before perfoming any operations.")

        tid = str(next(self._tids))

        future: asyncio.Future[tuple[str, str]] = self.loop.create_future()
        self._pending_requests[tid] = future

        try:
            # Acquire lock only for the write operation to allow pipelining.
            # Other commands can be sent while we wait for this specific TID's response.
            async with self._lock:
                await self._serial.write_async(f"{tid} {command}\n".encode('utf-8'))
                logger.info(
                    f"Sending Request: {command} with timeout {timeout if timeout else self.timeout} and transaction ID {tid}")

            _, response = await asyncio.wait_for(future, timeout if timeout else self.timeout)

            if matches := self._wait_re.search(response):
                requested_timeout: float = int(matches.group(
                    1))/1000 + timeout if timeout else self.timeout
                logger.info(
                    f"    ⤷ Arduino processing task, requires delay of {matches.group(1)}ms")
                future = self.loop.create_future()
                self._pending_requests[tid] = future
                asyncio.create_task(asyncio.wait_for(
                    future, requested_timeout))
                return response

            logger.success(
                f"    ⤷ Successfully processed request: '{command}' with response '{response}'")
            if response.endswith('ERR'):
                logger.warning(
                    f"        ⤷ Although request was successfully processed client-side, arduino has errored ({response})")

            return response
        except asyncio.TimeoutError:
            logger.error(f"    ⤷ Timed out awaiting response for: '{command}'")
            return "ERR_TIMED_OUT"
        except Exception as e:
            logger.error(f"    ⤷ Error during request '{command}': '{e}'")
            return f"ERR_{type(e).__name__}"

    # 1, debug led pin number
    async def verify_connection(self, retries: int | None = None):
        """Verify serial connectivity with the Arduino via PING/PONG.

        :param retries: Number of connection attempts before giving up.
        :returns: ``True`` if the handshake succeeded, ``False`` otherwise.
        :rtype: bool
        """
        logger.info("Establishing Serial interface...")

        for attempt in range(1, self.retries + 1):
            response: str = await self._request("PING")

            if response == "PONG":
                logger.success(
                    f"    ⤷ Connection established: Received '{response}'")
                self.is_connected = True
                return True

            logger.warning(
                f"    ⤷ Connection attempt {attempt}/{retries} failed ({response})")
            await asyncio.sleep(10 * self.timeout)

        logger.critical(
            "Failed to establish connection after multiple attempts.")
        return False

    async def set_servo_angle(self, angle: int) -> bool:  # 2
        """Set the servo to an absolute angle.

        Clamps *angle* to the configured min/max range before sending.

        :param angle: Desired servo angle in degrees.
        :returns: ``True`` if the command was acknowledged, ``False`` otherwise.
        :rtype: bool
        """
        if GLOBAL_CONFIG().ClientConfig.SERVO_MAX_ANGLE < angle:
            logger.warning(
                f"Invalid request clamped: 'SET_SERVO {angle}'. {angle} is not in [{GLOBAL_CONFIG().ClientConfig.SERVO_MIN_ANGLE}, {GLOBAL_CONFIG().ClientConfig.SERVO_MAX_ANGLE}]")
            angle = GLOBAL_CONFIG().ClientConfig.SERVO_MAX_ANGLE
        elif GLOBAL_CONFIG().ClientConfig.SERVO_MIN_ANGLE > angle:
            logger.warning(
                f"Invalid request clamped: 'SET_SERVO {angle}'. {angle} is not in [{GLOBAL_CONFIG().ClientConfig.SERVO_MIN_ANGLE}, {GLOBAL_CONFIG().ClientConfig.SERVO_MAX_ANGLE}]")
            angle = GLOBAL_CONFIG().ClientConfig.SERVO_MIN_ANGLE
        command: str = f'SET_SERVO {angle}'
        response: str = await self._request(command)
        return response == '200 OK' or response.startswith('WAITMS ')

    async def increment_servo_angle(self, increment: int) -> bool:  # 3
        """Adjust the servo angle by a relative increment.

        :param increment: Signed angle change in degrees.
        :returns: ``True`` if the command was acknowledged, ``False`` otherwise.
        :rtype: bool
        """
        command: str = f'INC_SERVO {increment}'
        response: str = await self._request(command)
        return response == '200 OK' or response.startswith('WAITMS ')

    async def set_motor_speed(self, speed: float, duration: float) -> bool:  # 4
        """Set the motor speed for a specified duration.

        :param speed: Normalized motor speed in ``[-1, 1]`` (scaled by ``max_speed``).
        :param duration: Motor run duration in seconds.
        :returns: ``True`` if the command was acknowledged, ``False`` otherwise.
        :rtype: bool
        """
        # changed api to be 0-1 instead of absolute don't think I need refactoring changes though
        speed = speed * self.max_speed
        command: str = f'SET_MOTOR {speed:.2f} {duration:.3f}'
        # Fallback timeout in case WAITMS is delayed or dropped under serial contention.
        request_timeout: float = max(
            GLOBAL_CONFIG().ClientConfig.REQUEST_TIMEOUT,
            abs(float(duration)) +
            GLOBAL_CONFIG().ClientConfig.WAIT_RESPONSE_EXTRA_SECONDS + 1.0,
        )
        response: str = await self._request(command, timeout=request_timeout)
        return response == '200 OK' or response.startswith('WAITMS ')

    # hybrid, no debug led pin number
    async def drive_motors(self, speed: float, angle: int, duration: float) -> bool:
        """Send a combined motor speed and servo angle command.

        Uses a bounded semaphore to prevent overlapping drive commands.
        Both sub-commands are issued concurrently via :func:`asyncio.gather`.

        :param speed: Normalized motor speed in ``[-1, 1]``.
        :param angle: Servo angle in degrees.
        :param duration: Motor run duration in seconds.
        :returns: ``True`` if both commands succeeded, ``False`` otherwise.
        :rtype: bool
        """
        if self._drive_semaphore.locked():
            return False

        async with self._drive_semaphore:
            promises: list[Coroutine[Any, Any, bool]] = []
            promises.append(self.set_motor_speed(speed, duration))
            promises.append(self.set_servo_angle(angle))

            results: list[bool] = await asyncio.gather(*promises)
            return all(results)

    async def get_servo_angle(self) -> bool:
        """Query the current servo angle from the Arduino.

        :returns: ``True`` if a valid integer angle was received, ``False`` otherwise.
        :rtype: bool
        """
        response: str = await self._request("SERVO_ANGLE")
        try:
            self.servo_angle = int(response)
            return True
        except ValueError:
            logger.warning(
                f"Received non-integer response '{response}' from request 'SERVO_ANGLE'")
            return False

    async def set_led_state(self, state: Literal[1, 0]) -> bool:  # 5
        """Set the debug LED on the Arduino.

        :param state: ``1`` for on, ``0`` for off.
        :returns: ``True`` if the command was acknowledged, ``False`` otherwise.
        :rtype: bool
        """
        command: str = f'SET_LED {state}'
        response: str = await self._request(command)
        return response == '200 OK'


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
        """Create an executor that sends commands through *client*.

        The executor owns a single background worker and stores at most one
        pending command, so newer submissions replace stale pending work.

        :param client: :class:`Client` used to transmit motor commands.
        :returns: ``None``.
        :rtype: None
        """
        self._client: Client = client
        self._pending: tuple[float, float, float] | None = None
        self._wakeup = asyncio.Event()
        self._worker_task: Task[NoReturn] | None = None

    async def __aenter__(self) -> Self:
        """Start the single background command worker.

        :returns: This initialized executor.
        :rtype: Self
        """
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Drive command executor started")
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Cancel and await the background command worker.

        :param args: Async context-manager exception information, accepted for
            protocol compatibility.
        :returns: ``None``.
        :rtype: None
        """
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
        self._pending = (speed, angle, duration)
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
            except Exception as e:
                logger.error(f"Drive command {command} failed: {e}")
