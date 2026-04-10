import aioserial
import numpy as np
import re
import time
from itertools import cycle
from loguru import logger


class Client():
    def __init__(self, port='/dev/ttyACM0', baud=115200, timeout=0.3):
        """
        The constructor for the `Client` class.

        :param port: The serial port passed to `aioserial.AioSerial`.
        :param baud: The baudrate of the serial protocol.
        :param timeout: Default timeout for granular requests.
        """
        self.SERIAL = None
        self.port = port
        self.baud = baud
        self.DEFAULT_TIMEOUT = timeout
        self.TIDS = cycle(range(1, 501))
        self.WHEELBASE = 0.1
        self.MAX_SPEED = 100
        self.WAIT_RE = re.compile(r"WAITMS ([0-9]+)")
        self.is_connected = False
        self.servo_angle = 0
        self.encoder_value = 0

        logger.info(
            f"======= CLIENT INSTANCE STARTED: Port = {port}, Baud = {baud}, Timeout = {timeout} ======= "
        )

    def __enter__(self):
        self.SERIAL = aioserial.AioSerial(
            port=self.port,
            baudrate=self.baud,
            timeout=self.DEFAULT_TIMEOUT,
            write_timeout=self.DEFAULT_TIMEOUT,
        )
        self.SERIAL.reset_input_buffer()
        self.SERIAL.reset_output_buffer()
        logger.info("Serial interface started")
        return self

    def __exit__(self, *args):
        if self.SERIAL is not None:
            self.SERIAL.close()
            self.SERIAL = None
            logger.info("Serial interface closed")

    def _read_response(self, tid, timeout):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            line = self.SERIAL.readline()
            if not line:
                continue

            response = line.decode('utf-8', errors='replace').strip()
            logger.debug(f"Line read from serial buffer: '{response}'")

            parts = response.split(" ", 1)
            if len(parts) < 2:
                continue

            response_tid, message = parts
            if response_tid == tid:
                return message

            logger.warning(f"Ignoring out-of-order response for transaction ID {response_tid}")

        raise TimeoutError(f"Timed out waiting for transaction ID {tid}")

    def _request(self, command, timeout=2.0):
        tid = str(next(self.TIDS))

        try:
            self.SERIAL.write(f"{tid} {command}\n".encode('utf-8'))
            self.SERIAL.flush()
            logger.info(f"Sending Request: {command} with timeout {timeout} and transaction ID {tid}")

            response = self._read_response(tid, timeout)

            if matches := self.WAIT_RE.search(response):
                requested_timeout = int(matches.group(1)) / 1000 + 0.5
                logger.info(f"    -> Arduino processing task, requires delay of {matches.group(1)}ms")
                response = self._read_response(tid, requested_timeout)

            logger.success(f"    -> Successfully processed request: '{command}' with response '{response}'")
            if response.endswith('ERR'):
                logger.warning(
                    f"        -> Although request was successfully processed client-side, arduino has errored ({response})"
                )

            return response
        except TimeoutError:
            logger.error(f"    -> Timed out awaiting response for: '{command}'")
            return "ERR_TIMED_OUT"
        except Exception as e:
            logger.error(f"    -> Error during request '{command}': '{e}'")
            return f"ERR_{type(e).__name__}"

    def run_multiple_requests(self, requests, timeout=2.0):
        raise NotImplementedError("Batch requests not yet supported server-side.")

    def verify_connection(self, retries=5):
        logger.info("Establishing Serial interface...")

        for attempt in range(1, retries + 1):
            response = self._request("PING", timeout=2.0)

            if response == "PONG":
                logger.success(f"    -> Connection established: Received '{response}'")
                self.is_connected = True
                return True

            logger.warning(f"    -> Connection attempt {attempt}/{retries} failed ({response})")
            time.sleep(0.5)

        logger.critical("Failed to establish connection after multiple attempts.")
        return False

    def set_servo_angle(self, angle):
        if angle > 180:
            logger.warning(f"Invalid request clamped: 'SET_SERVO {angle}'. {angle} is not in [-180, 180]")
            angle = 180
        elif angle < -180:
            logger.warning(f"Invalid request clamped: 'SET_SERVO {angle}'. {angle} is not in [-180, 180]")
            angle = -180

        response = self._request(f'SET_SERVO {angle}')
        return response == '200 OK'

    def increment_servo_angle(self, increment):
        response = self._request(f'INC_SERVO {increment}')
        return response == '200 OK'

    def set_motor_speed(self, speed, duration):
        scaled_speed = speed * self.MAX_SPEED
        response = self._request(f'SET_MOTOR {scaled_speed} {duration}')
        return response == '200 OK'

    def drive_motors(self, speed: float, angle: float, duration: float):
        motor_ok = self.set_motor_speed(speed, duration)
        servo_ok = self.set_servo_angle(angle)
        return motor_ok and servo_ok

    def get_servo_angle(self):
        response = self._request("SERVO_ANGLE")
        try:
            self.servo_angle = int(response)
            return True
        except ValueError:
            logger.warning(f"Received non-integer response '{response}' from request 'SERVO_ANGLE'")
            return False

    def set_led_state(self, state):
        response = self._request(f'SET_LED {state}')
        return response == '200 OK'

