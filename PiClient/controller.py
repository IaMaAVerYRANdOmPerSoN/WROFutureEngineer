from loguru import logger

class PD(): # No i needed, works fine in past seasons
    def __init__(self, kp, kd):
        self.kp = kp
        self.kd = kd
        self.previous_error = 0

    def tick(self, target, value):
        error = target - value
        proportional = self.kp * error
        derrivative = self.kd * (error - self.previous_error)

        self.previous_error = error
        logger.info(f"PD output: Propotional {proportional}, Derrivative {derrivative}, Total {proportional + derrivative}")
        return proportional + derrivative