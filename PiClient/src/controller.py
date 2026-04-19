from loguru import logger


class PD():  # No i needed, works fine in past seasons
    def __init__(self, kp, kd):
        self.KP = kp
        self.KD = kd
        self.previous_error = 0

    def tick(self, target, value=None):
        error = target if value is None else target - value
        proportional = self.KP * error
        derivative = self.KD * (error - self.previous_error)

        self.previous_error = error
        logger.info(
            f"PD output: Proportional {proportional}, Derivative {derivative}, Total {proportional + derivative}")
        return proportional + derivative
