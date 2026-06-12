"""Control library.

Provides :class:`PD`, a simple proportional-derivative controller.
"""

from src import logger


class PD():
    """Proportional-Derivative (PD) controller.

    A simple PD controller with no integral term. Suitable for
    wall-following, corner turning, and obstacle avoidance.

    :ivar KP: Proportional gain.
    :ivar KD: Derivative gain.
    :ivar previous_error: Error from the previous :meth:`tick` call.
    """

    def __init__(self, kp, kd):
        """Initialise the PD controller.

        :param kp: Proportional gain.
        :param kd: Derivative gain.
        """
        self.KP = kp
        self.KD = kd
        self.previous_error = 0

    def tick(self, target, value=None):
        """Compute one PD iteration.

        If *value* is ``None``, *target* is treated as the error directly
        (e.g. when tracking a difference signal).

        :param target: Desired setpoint, or the error signal if *value* is ``None``.
        :param value: Current measured value (optional).
        :returns: Control output (proportional + derivative).
        :rtype: float
        """
        error = target if value is None else target - value
        proportional = self.KP * error
        derivative = self.KD * (error - self.previous_error)

        self.previous_error = error
        logger.info(
            f"PD output: Proportional {proportional:.3f}, Derivative {derivative:.3f}, Total {(proportional + derivative):.3f}")
        return proportional + derivative
