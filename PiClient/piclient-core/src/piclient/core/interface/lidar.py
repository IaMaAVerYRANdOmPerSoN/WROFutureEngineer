"""LD19 LiDAR interface.

Provides :class:`LiDARPacket` for parsed LD19 data and :class:`LiDAR`
for async serial reading, packet parsing, and point-cloud extraction.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from dataclasses import dataclass
import struct
import numpy as np
from collections.abc import Generator, Sequence
from typing import Any, NoReturn, Self

import aioserial  # pyright: ignore[reportMissingTypeStubs]

from .. import logger
from ..lib import Config, export

from multiprocessing.connection import PipeConnection


@export
@dataclass
class LiDARPacket:
    """
    Represents a single LD19 LiDAR packet with parsed fields.

    :ivar speed: Rotational speed in RPM.
    :vartype speed: float
    :ivar start_angle: Starting angle of the scan in degrees.
    :vartype start_angle: float
    :ivar end_angle: Ending angle of the scan in degrees.
    :vartype end_angle: float
    :ivar timestamp: Timestamp from the LiDAR in milliseconds.
    :vartype timestamp: int
    :ivar crc: CRC byte from the packet for integrity checking.
    :vartype crc: int
    :ivar points: list of measurement points, each containing:
    :vartype points: list[dict[str, Any]]
    """
    speed: float
    start_angle: float
    end_angle: float
    timestamp: int
    crc: int
    points: list[dict[str, Any]]


@export
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
        self._serial: aioserial.AioSerial | None = None
        self.PORT = port
        self.BAUD = baud
        self.DEFAULT_TIMEOUT = timeout
        self.PACKET_LEN = packet_len

        self._buffer = bytearray()
        self._latest_packet: LiDARPacket | None = None
        self._data_lock = asyncio.Lock()
        self._packet_event = asyncio.Event()

        logger.info(
            f"======= LIDAR INSTANCE STARTED: Port = {self.PORT}, Baud = {self.BAUD}, Timeout = {self.DEFAULT_TIMEOUT} ======="
        )

    def _find_packet_start(self, buffer: bytearray) -> int:
        """Locate the start of a valid LD19 packet in the buffer.

        Scans for the packet header byte (``0x54``) followed by the
        expected version/length byte (``0x2C``).

        :param buffer: Raw byte buffer from the serial stream.
        :returns: Index of the packet start, or ``-1`` if not found.
        """
        for i in range(len(buffer) - 1):
            if buffer[i] == self.PACKET_HEADER and (buffer[i + 1] & 0xFF) == self.VER_LEN:
                return i
        return -1

    def _convert_to_xy(self, coords: Sequence[tuple[float, float]]) -> Generator[tuple[float, float], None, None]:
        """Convert polar (distance, angle) pairs to Cartesian (x, y).

        :param coords: Sequence of ``(distance_mm, angle_deg)`` tuples.
        :yields: ``(x_mm, y_mm)`` tuples.
        """
        for r, theta in coords:
            x = r * np.cos(np.deg2rad(theta))
            y = r * np.sin(np.deg2rad(theta))
            yield (x, y)

    def _parse_packet(self, packet: bytes) -> LiDARPacket | None:
        """Parse a raw 47-byte LD19 packet into a :class:`LiDARPacket`.

        Extracts speed, angles, timestamp, CRC, and 12 measurement points
        with interpolated angles.

        :param packet: Raw 47-byte packet from the serial stream.
        :returns: Parsed :class:`LiDARPacket`, or ``None`` if invalid.
        """
        if len(packet) != self.PACKET_LEN:
            return None

        speed = struct.unpack_from("<H", packet, 2)[0] / 64.0
        start_angle = struct.unpack_from("<H", packet, 4)[0] / 100.0

        measurements: list[tuple[float, float]] = []
        for i in range(12):
            offset = 6 + i * 3
            dist = struct.unpack_from("<H", packet, offset)[0]
            confidence = packet[offset + 2]
            measurements.append((dist, confidence))

        end_angle = struct.unpack_from("<H", packet, 42)[0] / 100.0
        timestamp = struct.unpack_from("<H", packet, 44)[0]
        crc = packet[46]

        angles = self._interpolate_angles(start_angle, end_angle, 12)
        points = self._convert_to_xy(
            [(dist, angle) for (dist, _), angle in zip(measurements, angles)])

        return LiDARPacket(
            speed=speed,
            start_angle=start_angle,
            end_angle=end_angle,
            timestamp=timestamp,
            crc=crc,
            points=[{"x": x, "y": y, "confidence": confidence}
                    for (x, y), (_, confidence) in zip(points, measurements)],
        )

    @staticmethod
    def _interpolate_angles(start: float, end: float, count: int) -> list[float]:
        """Linearly interpolate angles between start and end (wrapping 360°).

        :param start: Start angle in degrees.
        :param end: End angle in degrees.
        :param count: Number of interpolation points.
        :returns: list of interpolated angles in degrees.
        """
        angle_range = (end - start + 360.0) % 360.0
        step = angle_range / (count - 1)
        return [((start + i * step) % 360.0) for i in range(count)]

    async def _serial_listener(self) -> NoReturn:
        """Background task that reads raw bytes and parses LD19 packets.

        Accumulates chunks into :attr:`_buffer`, extracts full packets,
        parses them, and stores the latest packet in :attr:`_latest_packet`.
        Sets :attr:`_packet_event` when a new packet is available.
        """
        assert self._serial is not None, "Serial interface not initialized. Did you forget to use the async context manager?"

        while True:
            try:
                chunk = await self._serial.read_async(256)
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

    async def __aenter__(self, *args: Any) -> Self:
        self._serial = aioserial.AioSerial(
            self.PORT, self.BAUD, timeout=self.DEFAULT_TIMEOUT)

        if not hasattr(self, "_listener_task"):
            self._listener_task = asyncio.create_task(self._serial_listener())
            logger.info("LiDAR serial listener started")
        else:
            logger.warning(
                "LiDAR serial listener already started in this context")

        return self

    async def __aexit__(self, *args: Any) -> None:
        if hasattr(self, "_listener_task"):
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

            if self._serial is not None:
                self._serial.close()

            logger.info("LiDAR serial listener terminated")
        else:
            logger.warning("No LiDAR serial listener to cancel")

    async def reload(self) -> Self:
        """Hot reload after changing attributes.

        Tears down existing hardware resources, reinitialises them
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

    async def capture_packet(self, timeout: float = 1.0) -> bool:
        """Wait for the next available LiDAR packet.

        Clears :attr:`_packet_event` and waits for the listener to set it.

        :param timeout: Maximum wait time in seconds.
        :returns: ``True`` if a new packet was captured, ``False`` on timeout.
        :rtype: bool
        """
        self._packet_event.clear()
        try:
            await asyncio.wait_for(self._packet_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def get_latest_packet(self) -> LiDARPacket | None:
        async with self._data_lock:
            if self._latest_packet is None:
                return None
            return self._latest_packet

    async def stream_packets(self, sender: PipeConnection, timeout: float = 1.0) -> NoReturn:
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
    async def async_pipe_reader(receiver: PipeConnection):
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
    def lidar_process_context_manager(sender: PipeConnection):
        async def _run(sender: PipeConnection):
            async with LiDAR() as lidar:
                await lidar.stream_packets(sender)
        asyncio.run(_run(sender))
