import asyncio
import sys
from typing import cast
from multiprocessing.connection import Connection
from src import logger
from src.modules.comm_protocol import Client
from src.modules.lidar import LiDAR, LiDARPacket
import multiprocessing as mp
import numpy as np
import cv2

async def run_tests():
    async with Client() as client:
        try:
            data_receiver, data_sender = mp.Pipe(duplex=False)
            lidar_process = mp.Process(target=LiDAR.lidar_process_context_manager, args=(data_sender,))
            lidar_process.start()

            async for packet in LiDAR.async_pipe_reader(cast(Connection, data_receiver)):
                assert packet is not None, "Received None packet"
                assert isinstance(packet, LiDARPacket), f"Received packet of incorrect type: {type(packet)}"
                assert isinstance(packet.speed, float), f"Packet speed is not a float: {type(packet.speed)}"
                assert isinstance(packet.timestamp, float), f"Packet timestamp is not a float: {type(packet.timestamp)}"
                assert isinstance(packet.start_angle, float), f"Packet angle is not a float: {type(packet.start_angle)}"
                assert isinstance(packet.end_angle, float), f"Packet distance is not a float: {type(packet.end_angle)}"
                assert isinstance(packet.crc, int), f"Packet intensity is not an int: {type(packet.crc)}"
                assert isinstance(packet.points, list) and all(isinstance(point, dict) for point in packet.points), f"Packet distances is not a list of floats: {type(packet.points)} with elements {[type(point) for point in packet.points]}"

                logger.info(f"Received LiDAR packet: {packet}")

                frame = np.zeros((500, 500, 3), dtype=np.uint8)
                for point in packet.points:
                    x = int(point["x"] / 1000 * 250 + 250)
                    y = int(250 - point["y"] / 1000 * 250)
                    confidence = point["confidence"]
                    color = (0, confidence, 255 - confidence)
                    cv2.circle(frame, (x, y), 3, color, -1)

                cv2.imshow("LiDAR Feed", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        except Exception as e:
            logger.error(f"Error during LiDAR test: {e}")
            raise RuntimeError(f"LiDAR test failed") from e
        finally:
            logger.info("Terminating LiDAR process")
            lidar_process.terminate()
            lidar_process.join(timeout=1)
            lidar_process.kill()
            logger.info("LiDAR process terminated")
