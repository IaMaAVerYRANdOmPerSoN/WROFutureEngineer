import asyncio
from concurrent.futures import ThreadPoolExecutor

from dataclasses import dataclass
import struct
import numpy as np
from typing import Any, Dict, Generator, List, NoReturn, Optional, Sequence, Tuple

import aioserial

from src import logger
from src.modules.config import Config

from multiprocessing.connection import Connection


@dataclass
class LiDARPacket:
    """
    Represents a single LD19 LiDAR packet with parsed fields.
    Attributes:
        speed (float): Rotational speed in RPM.
        start_angle (float): Starting angle of the scan in degrees.
        end_angle (float): Ending angle of the scan in degrees.
        timestamp (int): Timestamp from the LiDAR in milliseconds.
        crc (int): CRC byte from the packet for integrity checking.
        points (List[Dict[str, Any]]): List of measurement points, each containing:
            - x (float): X coordinate in millimeters.
            - y (float): Y coordinate in millimeters.
            - confidence (int): Confidence level of the measurement (0-255).
    """
    speed: float
    start_angle: float
    end_angle: float
    timestamp: int
    crc: int
    points: List[Dict[str, Any]]


class LiDAR:
    """Async LD19 LiDAR reader.

    The parser matches the LD19 packet layout:
    - Byte 0: packet header (0x54)
    - Byte 1: ver/len byte (expected 0x2C)
    - Bytes 2-45: payload
    - Byte 46: crc
    """

    PACKET_HEADER = Config.LiDARConfig.PACKET_HEADER
    VER_LEN = Config.LiDARConfig.PACKET_VER_LEN

    def __init__(
        self,
        port: str = Config.LiDARConfig.SERIAL_PORT,
        baud: int = Config.LiDARConfig.SERIAL_BAUD,
        timeout: float = Config.LiDARConfig.SERIAL_TIMEOUT,
        packet_len: int = Config.LiDARConfig.PACKET_LEN,
    ) -> None:
        self.SERIAL: Optional[aioserial.AioSerial] = None
        self.PORT = port
        self.BAUD = baud
        self.DEFAULT_TIMEOUT = timeout
        self.PACKET_LEN = packet_len

        self._buffer = bytearray()
        self._latest_packet: Optional[LiDARPacket] = None
        self._data_lock = asyncio.Lock()
        self._packet_event = asyncio.Event()

        logger.info(
            f"======= LIDAR INSTANCE STARTED: Port = {self.PORT}, Baud = {self.BAUD}, Timeout = {self.DEFAULT_TIMEOUT} ======="
        )

    def _find_packet_start(self, buffer: bytearray) -> int:
        for i in range(len(buffer) - 1):
            if buffer[i] == self.PACKET_HEADER and (buffer[i + 1] & 0xFF) == self.VER_LEN:
                return i
        return -1
    
    def _convert_to_xy(self, coords: Sequence[Tuple[float, float]]) -> Generator[Tuple[float, float], None, None]:
        for r, theta in coords:
            x = r * np.cos(np.deg2rad(theta))
            y = r * np.sin(np.deg2rad(theta))
            yield (x, y)

    def _parse_packet(self, packet: bytes) -> Optional[LiDARPacket]:
        if len(packet) != self.PACKET_LEN:
            return None

        speed = struct.unpack_from("<H", packet, 2)[0] / 64.0
        start_angle = struct.unpack_from("<H", packet, 4)[0] / 100.0

        measurements = []
        for i in range(12):
            offset = 6 + i * 3
            dist = struct.unpack_from("<H", packet, offset)[0]
            confidence = packet[offset + 2]
            measurements.append((dist, confidence))

        end_angle = struct.unpack_from("<H", packet, 42)[0] / 100.0
        timestamp = struct.unpack_from("<H", packet, 44)[0]
        crc = packet[46]

        angles = self._interpolate_angles(start_angle, end_angle, 12)
        points = self._convert_to_xy([(dist, angle) for (dist, _), angle in zip(measurements, angles)])

        return LiDARPacket(
            speed=speed,
            start_angle=start_angle,
            end_angle=end_angle,
            timestamp=timestamp,
            crc=crc,
            points=[{"x": x, "y": y, "confidence": confidence} for (x, y), (_, confidence) in zip(points, measurements)],
        )

    @staticmethod
    def _interpolate_angles(start: float, end: float, count: int) -> List[float]:
        angle_range = (end - start + 360.0) % 360.0
        step = angle_range / (count - 1)
        return [((start + i * step) % 360.0) for i in range(count)]

    async def _serial_listener(self) -> NoReturn:
        assert self.SERIAL is not None, "Serial interface not initialized. Did you forget to use the async context manager?"

        while True:
            try:
                chunk = await self.SERIAL.read_async(256)
            except Exception as e:
                logger.error(f"Error reading from serial: {e}")
                continue

            if not chunk:
                await asyncio.sleep(0.01)
                continue

            self._buffer.extend(chunk)

            while True:
                idx = self._find_packet_start(self._buffer)
                if idx == -1:
                    if len(self._buffer) > 1:
                        del self._buffer[:-1]
                    break

                if idx > 0:
                    del self._buffer[:idx]

                if len(self._buffer) < self.PACKET_LEN:
                    break

                packet = bytes(self._buffer[: self.PACKET_LEN])
                del self._buffer[: self.PACKET_LEN]

                parsed = self._parse_packet(packet)
                if not parsed:
                    logger.debug("Discarded invalid LD19 packet")
                    continue

                async with self._data_lock:
                    self._latest_packet = parsed
                    self._packet_event.set()

                logger.debug(
                    f"LD19 packet parsed: speed={parsed.speed:.2f} start={parsed.start_angle:.2f} end={parsed.end_angle:.2f}"
                )

    async def __aenter__(self) -> LiDAR:
        self.SERIAL = aioserial.AioSerial(
            self.PORT, self.BAUD, timeout=self.DEFAULT_TIMEOUT)

        if not hasattr(self, "_listener_task"):
            self._listener_task = asyncio.create_task(self._serial_listener())
            logger.info("LiDAR serial listener started")
        else:
            logger.warning(
                "LiDAR serial listener already started in this context")

        return self

    async def __aexit__(self, *args) -> None:
        if hasattr(self, "_listener_task"):
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

            if self.SERIAL is not None:
                self.SERIAL.close()

            logger.info("LiDAR serial listener terminated")
        else:
            logger.warning("No LiDAR serial listener to cancel")

    async def capture_packet(self, timeout: float = 1.0) -> bool:
        self._packet_event.clear()
        try:
            await asyncio.wait_for(self._packet_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def get_latest_packet(self) -> Optional[LiDARPacket]:
        async with self._data_lock:
            if self._latest_packet is None:
                return None
            return self._latest_packet

    async def stream_packets(self, sender: Connection, timeout: float = 1.0) -> NoReturn:
        pipe_executor = ThreadPoolExecutor(max_workers=2)
        loop = asyncio.get_running_loop()

        while True:
            if await self.capture_packet(timeout=timeout):
                packet = await self.get_latest_packet()
                if packet:
                    await loop.run_in_executor(pipe_executor, sender.send, packet)
            else:
                logger.warning("LiDAR packet capture timed out")

    @staticmethod
    async def async_pipe_reader(receiver: Connection):
        loop = asyncio.get_running_loop()

        try:
            data_event = asyncio.Event()

            def yielder():
                data_event.set()

            loop.add_reader(receiver.fileno(), yielder)

            try:
                while True:
                    await data_event.wait()

                    while receiver.poll():
                        yield receiver.recv()

                    data_event.clear()
            finally:
                loop.remove_reader(receiver.fileno())
        except NotImplementedError:
            while True:
                try:
                    data = await loop.run_in_executor(None, receiver.recv)
                except (EOFError, OSError):
                    break
                yield data

    @staticmethod
    def lidar_process_context_manager(sender):
        async def _run(sender: Connection):
            async with LiDAR() as lidar:
                await lidar.stream_packets(sender)
        asyncio.run(_run(sender))