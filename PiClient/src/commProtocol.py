import aioserial
import asyncio
import numpy as np
import re
from loguru import logger
from itertools import cycle
from typing import NoReturn
from src.config import Config


class Client():
    def __init__(self, port=Config.ClientConfig.SERIAL_PORT, baud=Config.ClientConfig.SERIAL_BAUD, timeout=Config.ClientConfig.SERIAL_TIMEOUT, ):
        """
        The constructor for the `Client` class

        :param self: The instance of Client
        :param port: The serial port passed to `aioserial.AioSerial`.
        :param baud: The baudrate of the serial protocol.
        :param timeout: Default timeout for granular requests.

        :returns self: an instance of `Client`
        """

        self.SERIAL = None
        self.PORT, self.BAUD = port, baud
        self.DEFAULT_TIMEOUT = timeout
        self.TIDS = cycle([i for i in range(
            Config.ClientConfig.TID_START, Config.ClientConfig.TID_END + 1)])
        self.WHEELBASE = Config.ClientConfig.WHEELBASE
        self.MAX_SPEED = Config.ClientConfig.MAX_SPEED
        self.WAIT_RE = re.compile(Config.ClientConfig.WAIT_RE_PATTERN)
        self.is_connected = False
        self.loop = asyncio.get_event_loop()
        self._pending_requests = {}  # {TID: future} -> {TID: response}
        self._lock = asyncio.Lock()
        self.servo_angle = 0
        self.encoder_value = 0

        logger.info(
            f"======= CLIENT INSTANCE STARTED: Port = {self.PORT}, Baud = {self.BAUD}, Timeout = {self.DEFAULT_TIMEOUT} ======= ")

    async def _serial_listener(self) -> NoReturn:
        """
        A background asynchronous serial listener that resolves serial IO dependent futures.

        :param self: The instance of `Client`
        :return: `NoReturn`
        """
        while True:
            line = await self.SERIAL.readline_async()
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
        Reserved function, automatically called on entering an `async with` or `async for` block. Intializes hardware resources
        asyncronously.

        :param self: The instance of
        :return: Description
        :rtype: list | list[str]
        """
        self.SERIAL = aioserial.AioSerial(
            self.PORT, self.BAUD, timeout=self.DEFAULT_TIMEOUT)

        if not hasattr(self, "_listener_task"):
            self._listener_task = asyncio.create_task(self._serial_listener())
            logger.info("Serial Listener Started")
        else:
            logger.warning("Serial listener already started in this context")
        return self

    async def __aexit__(self, *args):
        if hasattr(self, "_listener_task"):
            self._listener_task.cancel()
            self.SERIAL.close()
            logger.info("Serial listener terminated without errors")
        else:
            logger.warning("No serial listener to cancel")

    async def _request(self, command, timeout=Config.ClientConfig.REQUEST_TIMEOUT):
        tid = str(next(self.TIDS))

        future = self.loop.create_future()
        self._pending_requests[tid] = future

        try:
            async with self._lock:
                await self.SERIAL.write_async(f"{tid} {command}\n".encode('utf-8'))
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
                _, response = await asyncio.wait_for(future, requested_timeout)

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
        finally:
            self._pending_requests.pop(tid, None)

    # type annotaion because it's takes complicated arguments
    async def run_multiple_requests(self, requests, timeout=2.0):
        """data = {}
        inital_futures = []
        long_process_futures = []
        for command, *arguments in requests:
            if command not in data:
                data[command] = []
            data[command].append((tid := str(next(self.TIDS)), *arguments,))

            future = self.loop.create_future()
            self._pending_requests[tid] = future
            inital_futures.append(future)

        payload = json.dumps(data) + "\n"

        try:
            await self.SERIAL.write_async(payload.encode("utf-8"))
            logger.info(f"Sending batched requests (multiple requests with the same command are queued rather than overwritten):\n{data}")
            initial_results = await asyncio.wait_for(asyncio.gather(*inital_futures), timeout=timeout)

            for tid, result in initial_results:
                if matches := self.WAIT_RE.search(result):
                    requested_timeout = int(matches.group(1))/1000 + 0.5
                    future = self.loop.create_future()
                    self._pending_requests[tid] = future
                    long_process_futures.append(asyncio.wait_for(future, requested_timeout))
                else:
                    dummy = self.loop.create_future()
                    dummy.set_result((tid, result))
                    long_process_futures.append(dummy)
            return await asyncio.gather(*long_process_futures)
        except asyncio.TimeoutError:
            logger.error("Batch Timed Out")
            return ["ERR_TIMEOUT"] * len(requests)
        finally:
            for commands in data.values():
                for command in commands:
                    self._pending_requests.pop(command[0])"""
        raise NotImplementedError(
            "Batch requests not yet supported sever-side.")  # This isn't needed anyway lol

    # 1, debug led pin number
    async def verify_connection(self, retries=Config.ClientConfig.CONNECT_RETRIES):
        logger.info("Establishing Serial interface...")

        for attempt in range(1, retries + 1):
            response = await self._request("PING", timeout=Config.ClientConfig.REQUEST_TIMEOUT)

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
        if Config.ClientConfig.SERVO_MAX_ANGLE < angle:
            logger.warning(
                f"Invaild request clamped: 'SET_SERVO {angle}'. {angle} is not in [-180, 180]")
            angle = Config.ClientConfig.SERVO_MAX_ANGLE
        elif Config.ClientConfig.SERVO_MIN_ANGLE > angle:
            logger.warning(
                f"Invaild request clamped: 'SET_SERVO {angle}'. {angle} is not in [-180, 180]")
            angle = Config.ClientConfig.SERVO_MIN_ANGLE
        command = f'SET_SERVO {angle}'
        response = await self._request(command)
        return response == '200 OK'

    async def increment_servo_angle(self, increment):  # 3
        command = f'INC_SERVO {increment}'
        response = await self._request(command)
        return response == '200 OK'

    async def set_motor_speed(self, speed, duration):  # 4
        # changed api to be 0-1 instead of absolute don't think I need refactoring changes though
        speed = speed * self.MAX_SPEED
        command = f'SET_MOTOR {speed:.2f} {duration:.3f}'
        # Fallback timeout in case WAITMS is delayed or dropped under serial contention.
        request_timeout = max(
            Config.ClientConfig.REQUEST_TIMEOUT,
            abs(float(duration)) + Config.ClientConfig.WAIT_RESPONSE_EXTRA_SECONDS + 1.0,
        )
        response = await self._request(command, timeout=request_timeout)
        return response == '200 OK'

    # hybrid, no debug led pin number
    async def drive_motors(self, speed: float, angle: float, duration: float):
        promises = []
        promises.append(self.set_motor_speed(speed, duration))
        promises.append(self.set_servo_angle(angle))

        results = await asyncio.gather(*promises)
        return all(results)

    async def get_servo_angle(self):
        response = await self._request("SERVO_ANGLE")
        try:
            self.servo_angle = int(response)
            return True
        except ValueError:
            logger.warning(
                f"Received non-integer response '{response}' from request 'SERVO_ANGLE'")
            return False

    async def set_led_state(self, state):  # 5
        command = f'SET_LED {state}'
        response = await self._request(command)
        return response == '200 OK'
