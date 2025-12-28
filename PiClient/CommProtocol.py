import aioserial
import asyncio
import json
import numpy as np
from warnings import warn, simplefilter
import re
import sys
from loguru import logger
from itertools import cycle
from typing import Sequence
import 

simplefilter('always', RuntimeWarning)

class RaspberryPiClient():
    def __init__(self, port='/dev/ttyACM0', baud = 115200, timeout=0.3, log = "log.txt"):
        logger.remove()
        fmt = (
            "<blue>[{time:HH:mm:ss:SSS}]</blue> │ "
            "<cyan>{line:03}: {function: <18}</cyan> │ "
            "<level>{level: <8}</level> │ "
            "<level>{message}</level>")
        logger.add(sys.stderr, level="INFO", format=fmt) # Change to DEBUG for debug
        logger.add(log, enqueue=True, rotation="10 MB", retention="10 days", format=fmt)
        
        self.SERIAL = aioserial.AioSerial(port, baud)
        self.DEFAULT_TIMEOUT = timeout
        self.TIDS = cycle([i for i in range(1, 501)])
        self.WHEELBASE = 0.1 
        self.MAX_SPEED = 8
        self.WAIT_RE = re.compile(r"WAITMS ([0-9]+)")
        self.is_connected = False
        self.loop = asyncio.get_event_loop()
        self._pending_requests = {} # {TID: future} -> {TID: response}
        self.servo_angle = 0
        self.encoder_value = 0

        logger.info(f"======= CLIENT INSTANCE STARTED: Port = {port}, Baud = {baud}, Timeout = {timeout} ======= ")
    
    async def __serial_listener(self):
        while True:
            line = await self.SERIAL.readline_async()
            response = line.decode('utf-8').strip()

            logger.debug(f"Line read from serial buffer: '{response}'")
            
            parts = response.split(" ", 1)
            if len(parts) < 2: continue
            
            tid, message = parts[0], parts[1]
            
            if tid in self._pending_requests:
                future = self._pending_requests[tid]
                if not future.done():
                    future.set_result((tid, message))

    async def __aenter__(self):
        if not hasattr(self, "_listener_task"):
            self._listener_task = asyncio.create_task(self.__serial_listener())
            logger.info("Serial Listener Started")
        else:
            logger.warning("Serial listener already started in this context")
        return self
    
    async def __aexit__(self, *args):
        if hasattr(self, "_listener_task"):
            self._listener_task.cancel()
            logger.info("Serial listener terminated without errors")
        else:
            logger.warning("No serial listener to cancel")


    async def __request(self, command, timeout=2.0):
        tid = str(next(self.TIDS))
        
        future = self.loop.create_future()
        self._pending_requests[tid] = future
        
        try:
            await self.SERIAL.write_async(f"{tid} {command}\n".encode('utf-8'))
            logger.info(f"Sending Request: {command} with timeout {timeout} and transaction ID {tid}")
            
            response = await asyncio.wait_for(future, timeout)[1]
            
            if matches := self.WAIT_RE.search(response):
                requested_timeout = int(matches.group(1))/1000 + 0.5
                logger.info(f"    ⤷ Arduino processing task, requires delay of {matches.group(1)}ms")
                future = self.loop.create_future()
                self._pending_requests[tid] = future
                response = await asyncio.wait_for(future, requested_timeout + 0.5)[1]
            
            logger.success(f"    ⤷ Sucessfully processed request: '{command}' with response '{response}'")
            if response.endswith('ERR'):
                logger.warning(f"        ⤷ Although request was sucessfully proccessed client-side, arudino has errored ({response})")
                
            return response
        except asyncio.TimeoutError:
            logger.error(f"    ⤷ Timed out awaiting responce for: '{command}'")
            return "ERR_TIMED_OUT"
        except Exception as e:
            logger.error(f"    ⤷ Error during request '{command}': '{e}'")
            return f"ERR_{type(e).__name__}"
        finally:
            self._pending_requests.pop(tid, None)

    async def __run_multiple_requests(self, requests: Sequence[Sequence[str, float]|Sequence[str, float, float]], timeout = 2.0): # type annotaion because it's takes complicated arguments
        data = {}
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
                    self._pending_requests.pop(command[0])
            
    async def verify_connection(self, retries=5): # 1
        logger.info("Establishing Serial interface...")
        
        for attempt in range(1, retries + 1):
            response = await self.__request("PING", timeout=2.0)
            
            if response == "PONG":
                logger.success(f"    ⤷ Connection established: Received '{response}'")
                self.is_connected = True
                return True
            
            logger.warning(f"    ⤷ Connection attempt {attempt}/{retries} failed ({response})")
            await asyncio.sleep(0.5)

        logger.critical("Failed to establish connection after multiple attempts.")
        return False
    
    async def set_servo_angle(self, angle): # 2
        if 180 < angle or angle < -180:
            logger.warning(f"Invaild request blocked: 'SET_SERVO {angle}'. {angle} is not in [-180, 180]")
            return "ERR_ANGLE_UNBOUNDED"
        command = f'SET_SERVO {angle}'
        response =  await self.__request(command)
        return response == '200 OK'
    
    async def increment_servo_angle(self, increment): # 3
        command = f'INC_SERVO {increment}'
        response = await self.__request(command)
        return response == '200 OK'
    
    async def drive_motors(self, speed, duration): # 4
        duration = abs(duration) # No time travel sorry
        if speed > self.MAX_SPEED:
            warn(f"Speed Exceeds Practical Limits. Clamping to {self.MAX_SPEED}", RuntimeWarning)
            logger.warning(f"Invalid argument supplied: {speed} > {self.MAX_SPEED}. Clamped to {self.MAX_SPEED}")
            product = speed * duration
            speed = self.MAX_SPEED
            duration = product / speed
        command = f'DRIVE_MOTORS {speed} {duration}'
        response = await self.__request(command)
        return response == '200 OK'
    
    async def get_servo_angle(self):
        response = await self.__request("SERVO_ANGLE")
        try:
            self.servo_angle = int(response)
            return True
        except ValueError:
            logger.warning(f"Recived non-interger response '{response}' from request 'SERVO_ANGLE'")
        
        return False
    
    async def get_encoder_value(self):
        response = await self.__request("M_ANGLE")
        try:
            self.encoder_value = int(response)
            return True
        except ValueError:
            logger.warning(f"Recived non-interger response '{response}' from request 'M_ANGLE'")
        
        return False
        
    async def get_camera_data(self):
        raise NotImplementedError
    
    def __fast_arc_to_target(self, current_x, current_y, target_x, target_y, speed, current_heading_rad=0): 
        dx = target_x - current_x
        dy = target_y - current_y
        l_fw = np.sqrt(dx**2 + dy**2) 
        if l_fw < 1e-6:
            logger.warning(f'Zero division error ecountured in __fast_arc_to_target, with arguments {current_x, current_y, target_x, target_y, speed, current_heading_rad}')
            return 'ERR_ZERO_DIVISION'

        target_angle_global = np.arctan2(dx, dy) # Abosulte angle

        alpha = (target_angle_global - current_heading_rad + np.pi) % (2 * np.pi) - np.pi # Relative angle with normalisation
        kappa = (2 * np.sin(alpha)) / l_fw # Curvature
        
        # Output commands
        steering_angle_rad = np.arctan(self.WHEELBASE * kappa)
        duration = l_fw / speed if abs(kappa) < 1e-6 else (2 * alpha / kappa) / speed

        exit_angle_rad = (current_heading_rad + 2 * alpha) # exit angle
        
        return (steering_angle_rad, duration, exit_angle_rad)
    
    async def arc_spline(self, speed, points):
        current_x, current_y, current_hdg = 0.0, 0.0, 0.0
        
        commands = []
        for targetX, targetY in points:
            res = self.__fast_arc_to_target(current_x, current_y, targetX, targetY, speed, current_hdg)
            if isinstance(res, str): continue
            
            steer, duration, current_hdg = res
            commands.append((steer, duration))
            current_x, current_y = targetX, targetY
        
        for steer_rad, duration in commands:
            servo_angle = 90 + np.degrees(steer_rad) 
            await self.set_servo_angle(servo_angle)
            await self.drive_motors(speed, duration)
    
    async def set_led_state(self, state): #5
        command = f'SET_LED {state}'
        response = await self.__request(command)
        return response == '200 OK'

async def main():
    async with RaspberryPiClient() as client:
        await asyncio.sleep(2)
        if not await client.verify_connection():
            return
        
        await asyncio.sleep(0.5)

        while True:  
            drive_task = asyncio.create_task(client.arc_spline(7, [[1, 4], [3, 18], [6, 14], [7, 11], [7, 13], [7, 18], [8, 10], [10, 19], [11, 12], [13, 16]]))
            await asyncio.sleep(0) # let the task run

            for _ in range(100):
                await client.set_led_state(1.0)
                await client.get_servo_angle()
                await client.get_encoder_value()
                await client.set_led_state(0.0)
                await asyncio.sleep(0.1)
            
            try:
                await asyncio.wait_for(drive_task, timeout=30.0) # Will update this dynamically later
            except asyncio.TimeoutError:
                logger.warning(f"Drive task '{drive_task}' Timed out")
            
            await asyncio.sleep(0.15)

if __name__ == "__main__":
    try:
        asyncio.run(main())
        exitcode = 0
    except KeyboardInterrupt:
        logger.error("Process Interupted by User")
        exitcode = 0
    except Exception:
        logger.exception("A FATAL EXECPTION HAS OCCURED")
        exitcode = 1
    finally:
        logger.info(f"Cleaning up with exitcode {exitcode}...")
        logger.remove()
        sys.exit(exitcode)