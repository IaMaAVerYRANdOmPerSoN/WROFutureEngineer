"""Serial communication protocol client.

Provides :class:`Client` for request/response communication with the
Arduino over async serial, and :class:`DriveCommandExecutor` for
coalescing drive commands with latest-wins semantics.
"""

import aioserial
import asyncio
import re
from src import logger
from itertools import cycle
from typing import Literal, NoReturn, Tuple
from src.modules.lib.config import Config
from collections import defaultdict


class Client():
    """Async serial client for the Arduino communication protocol.

    Manages a TID-based request/response pipeline with a background
    serial listener. Supports motor, servo, LED, and ping commands.

    :ivar _serial: Underlying :class:`aioserial.AioSerial` instance.
    :ivar PORT: Serial port path.
    :ivar BAUD: Serial baud rate.
    :ivar DEFAULT_TIMEOUT: Default timeout for granular requests.
    :ivar TIDS: Cyclic transaction ID generator.
    :ivar is_connected: Whether the Arduino handshake has succeeded.
    """

    def __init__(self, port=Config.ClientConfig.SERIAL_PORT, baud=Config.ClientConfig.SERIAL_BAUD, timeout=Config.ClientConfig.SERIAL_TIMEOUT, ):
        """
        The constructor for the `Client` class

        :param self: The instance of Client
        :param port: The serial port passed to `aioserial.AioSerial`.
        :param baud: The baudrate of the serial protocol.
        :param timeout: Default timeout for granular requests.

        :returns self: an instance of `Client`
        """

        self._serial = None
        self.PORT, self.BAUD = port, baud
        self.DEFAULT_TIMEOUT = timeout
        self.TIDS = cycle([i for i in range(
            Config.ClientConfig.TID_START, Config.ClientConfig.TID_END + 1)])
        self.WHEELBASE = Config.ClientConfig.WHEELBASE
        self.MAX_SPEED = Config.ClientConfig.MAX_SPEED
        self.WAIT_RE = re.compile(Config.ClientConfig.WAIT_RE_PATTERN)
        self.is_connected = False
        self.loop = asyncio.get_event_loop()
        self._pending_requests: defaultdict[str, asyncio.Future[Tuple[str, str]]] = defaultdict(asyncio.Future)  # {TID: future} -> {TID: response}
        self._lock = asyncio.Lock()
        self._drive_semaphore = asyncio.BoundedSemaphore(1)
        self.servo_angle = 0
        self.encoder_value = 0

        logger.info(
            f"======= CLIENT INSTANCE STARTED: Port = {self.PORT}, Baud = {self.BAUD}, Timeout = {self.DEFAULT_TIMEOUT} ======= ")

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
            line = await self._serial.readline_async()
            response = line.decode('utf-8').strip()

            logger.debug(f"Line read from serial buffer: '{response}'")

            parts = response.split(" ", 1)
            if len(parts) < 2:
                continue

            tid, message = parts[0], parts[1]

            if tid in self._pending_requests:
                future = self._pending_requests[tid]
                if not future.done():
                    future.set_result((tid, message))

    async def __aenter__(self):
        """
        Async context manager entry point that initializes the serial interface
        and starts the background serial listener task.

        :param self: The instance of `Client`
        :return: The current `Client` instance.
        :rtype: Client
        """
        self._serial = aioserial.AioSerial(
            self.PORT, self.BAUD, timeout=self.DEFAULT_TIMEOUT)
        
        loop = asyncio._get_running_loop()
        loop.set_exception_handler(lambda loop, context: None)

        if not hasattr(self, "_listener_task"):
            self._listener_task = asyncio.create_task(self._serial_listener())
            logger.info("Serial Listener Started")
        else:
            logger.warning("Serial listener already started in this context")
        return self

    async def __aexit__(self, *args):
        if hasattr(self, "_listener_task"):
            self._listener_task.cancel()
            self._serial.close() if self._serial else None
            logger.info("Serial listener terminated without errors")
        else:
            logger.warning("No serial listener to cancel")

    async def _request(self, command, type, timeout=Config.ClientConfig.REQUEST_TIMEOUT):
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
            raise AttributeError("Please Use the Client's aysnc context manager to initilize hardware resources before perfoming any operations.")

        tid = str(next(self.TIDS))

        future: asyncio.Future[Tuple[str, str]]= self.loop.create_future()
        self._pending_requests[tid] = future

        try:
            # Acquire lock only for the write operation to allow pipelining.
            # Other commands can be sent while we wait for this specific TID's response.
            async with self._lock:
                await self._serial.write_async(f"{tid} {command}\n".encode('utf-8'))
                logger.info(
                    f"Sending Request: {command} with timeout {timeout} and transaction ID {tid}")

            _, response = await asyncio.wait_for(future, timeout)

            if matches := self.WAIT_RE.search(response):
                requested_timeout = int(matches.group(
                    1))/1000 + Config.ClientConfig.WAIT_RESPONSE_EXTRA_SECONDS
                logger.info(
                    f"    ⤷ Arduino processing task, requires delay of {matches.group(1)}ms")
                future = self.loop.create_future()
                self._pending_requests[tid] = future
                asyncio.create_task(asyncio.wait_for(future, requested_timeout))
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
    async def verify_connection(self, retries=Config.ClientConfig.CONNECT_RETRIES):
        """Verify serial connectivity with the Arduino via PING/PONG.

        :param retries: Number of connection attempts before giving up.
        :returns: ``True`` if the handshake succeeded, ``False`` otherwise.
        :rtype: bool
        """
        logger.info("Establishing Serial interface...")

        for attempt in range(1, retries + 1):
            response = await self._request("PING", 'PING', timeout=Config.ClientConfig.REQUEST_TIMEOUT)

            if response == "PONG":
                logger.success(
                    f"    ⤷ Connection established: Received '{response}'")
                self.is_connected = True
                return True

            logger.warning(
                f"    ⤷ Connection attempt {attempt}/{retries} failed ({response})")
            await asyncio.sleep(Config.ClientConfig.CONNECT_RETRY_SLEEP_SECONDS)

        logger.critical(
            "Failed to establish connection after multiple attempts.")
        return False

    async def set_servo_angle(self, angle):  # 2
        """Set the servo to an absolute angle.

        Clamps *angle* to the configured min/max range before sending.

        :param angle: Desired servo angle in degrees.
        :returns: ``True`` if the command was acknowledged, ``False`` otherwise.
        :rtype: bool
        """
        if Config.ClientConfig.SERVO_MAX_ANGLE <= angle:
            logger.warning(
                f"Invalid request clamped: 'SET_SERVO {angle}'. {angle} is not in [{Config.ClientConfig.SERVO_MIN_ANGLE}, {Config.ClientConfig.SERVO_MAX_ANGLE}]")
            angle = Config.ClientConfig.SERVO_MAX_ANGLE
        elif Config.ClientConfig.SERVO_MIN_ANGLE >= angle:
            logger.warning(
                f"Invalid request clamped: 'SET_SERVO {angle}'. {angle} is not in [{Config.ClientConfig.SERVO_MIN_ANGLE}, {Config.ClientConfig.SERVO_MAX_ANGLE}]")
            angle = Config.ClientConfig.SERVO_MIN_ANGLE
        command = f'SET_SERVO {angle}'
        response = await self._request(command, 'SET_SERVO')
        return response == '200 OK' or response.startswith('WAITMS ')

    async def increment_servo_angle(self, increment):  # 3
        """Adjust the servo angle by a relative increment.

        :param increment: Signed angle change in degrees.
        :returns: ``True`` if the command was acknowledged, ``False`` otherwise.
        :rtype: bool
        """
        command = f'INC_SERVO {increment}'
        response = await self._request(command, 'INC_SERVO')
        return response == '200 OK' or response.startswith('WAITMS ')

    async def set_motor_speed(self, speed, duration):  # 4
        """Set the motor speed for a specified duration.

        :param speed: Normalized motor speed in ``[-1, 1]`` (scaled by ``MAX_SPEED``).
        :param duration: Motor run duration in seconds.
        :returns: ``True`` if the command was acknowledged, ``False`` otherwise.
        :rtype: bool
        """
        # changed api to be 0-1 instead of absolute don't think I need refactoring changes though
        speed = speed * self.MAX_SPEED
        command = f'SET_MOTOR {speed:.2f} {duration:.3f}'
        # Fallback timeout in case WAITMS is delayed or dropped under serial contention.
        request_timeout = max(
            Config.ClientConfig.REQUEST_TIMEOUT,
            abs(float(duration)) +
            Config.ClientConfig.WAIT_RESPONSE_EXTRA_SECONDS + 1.0,
        )
        response = await self._request(command, 'SET_MOTOR', timeout=request_timeout)
        return response == '200 OK' or response.startswith('WAITMS ')

    # hybrid, no debug led pin number
    async def drive_motors(self, speed: float, angle: float, duration: float):
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
            promises = []
            promises.append(self.set_motor_speed(speed, duration))
            promises.append(self.set_servo_angle(angle))

            results = await asyncio.gather(*promises)
            return all(results)

    async def get_servo_angle(self):
        """Query the current servo angle from the Arduino.

        :returns: ``True`` if a valid integer angle was received, ``False`` otherwise.
        :rtype: bool
        """
        response = await self._request("SERVO_ANGLE", "SERVO_ANGLE")
        try:
            self.servo_angle = int(response)
            return True
        except ValueError:
            logger.warning(
                f"Received non-integer response '{response}' from request 'SERVO_ANGLE'")
            return False

    async def set_led_state(self, state: Literal[1, 0]):  # 5
        """Set the debug LED on the Arduino.

        :param state: ``1`` for on, ``0`` for off.
        :returns: ``True`` if the command was acknowledged, ``False`` otherwise.
        :rtype: bool
        """
        command = f'SET_LED {state}'
        response = await self._request(command, 'SET_LED')
        return response == '200 OK'


class DriveCommandExecutor():
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

    def __init__(self, client: "Client"):
        """
        :param client: The `Client` whose `drive_motors` the worker will call.
        """
        self._client = client
        self._pending: Tuple[float, float, float] | None = None
        self._wakeup = asyncio.Event()
        self._worker_task = None

    async def __aenter__(self):
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Drive command executor started")
        return self

    async def __aexit__(self, *args):
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Drive command executor stopped")

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

            command = self._pending
            self._pending = None
            if command is None:
                continue

            try:
                await self._client.drive_motors(*command)
            except Exception as e:
                logger.error(f"Drive command {command} failed: {e}")