import aioserial
import time
import asyncio
import numpy as np
from warnings import warn

class RaspberryPiClient():
    def __init__(self, serial=aioserial.AioSerial('/dev/ttyACM0', 115200, timeout=1)):
        self.SERIAL = serial
        self.WHEELBASE = 0.1  # meters
        self.WHEELBASE45DEG = self.WHEELBASE / np.sqrt(2)
        self.MAX_SPEED = 8 
    
    async def __request(self, command):
        await self.SERIAL.write((command + '\n').encode('utf-8'))
        try:
            response = await self.SERIAL.readline().decode('utf-8').strip()
        except Exception as e:
            warn(f"Caught Serial Protocal Exception: {e}")
            return f"ERR_{e}"
        return response
    
    async def set_servo_angle(self, angle):
        if 180 < angle or angle < -180:
            return "ERR_ANGLE_UNBOUNDED"
        command = f'SET_SERVO {angle}'
        response =  await self.__request(command)
        return response == '200 OK'
    
    async def increment_servo_angle(self, increment):
        command = f'INC_SERVO {increment}'
        response = await self.__request(command)
        return response == '200 OK'
    
    async def drive_motors(self, speed, duration): 
        duration = abs(duration) # No time travel sorry
        if speed > self.MAX_SPEED:
            warn(f"Speed Exceeds Practical Limits. Clamping to {self.MAX_SPEED}", RuntimeWarning)
            product = speed * duration
            speed = self.MAX_SPEED
            duration = product / speed
        command = f'DRIVE_MOTORS {speed} {duration}'
        response = await self.__request(command)
        return response == '200 OK'
    
    async def fast_arc_to_target(self, target_x, target_y, speed):
        l_fw = np.sqrt(target_x**2 + target_y**2) # Distance to target
        if l_fw < 1e-6:
            warn("Divsion by zero in fast_arc_to_target", RuntimeWarning)
            return 'ERR_ZERO_DIVSIION'
        alpha = np.arctan2(target_x, target_y) # Delta theta
        kappa = (2 * np.sin(alpha)) / l_fw # Curvature
        
        steering_angle_rad = np.arctan(self.WHEELBASE * kappa) # Steering angle in radians
        servo_deg = 90 + np.degrees(steering_angle_rad) # Convert to servo degrees
        duration = l_fw / speed if abs(kappa) < 1e-6 else (2 * alpha / kappa) / speed

        result1 = await self.set_servo_angle(servo_deg)
        result2 = await self.drive_motors(speed, duration)
        return (result1 and result2)

    
    async def arc_move(self, theta, radius, speed):
        if radius < 1e-6 or speed < 1e-6:
            warn("Divsion by zero in arc_move", RuntimeWarning)
            return 'ERR_ZERO_DIVISION'
        
        steering_delta = np.arctan(self.WHEELBASE / radius)
        distance = radius * theta
        duration = distance / speed
        servo_command_deg = np.degrees(steering_delta)

        result1 = await self.set_servo_angle(90 + servo_command_deg)
        result2 = await self.drive_motors(speed, duration)
        result3 = await self.set_servo_angle(90)
        return (result1 and result2 and result3)
        
    
    async def set_led_state(self, state):
        command = f'SET_LED {state}'
        response = await self.__request(command)
        return response == '200 OK'