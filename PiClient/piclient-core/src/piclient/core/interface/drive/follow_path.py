"""Latest-wins executor for following robot-relative waypoint paths."""
from typing import NoReturn

import asyncio
import math
import time

import numpy as np

from loguru import logger
from .client import Client
from .drive import DriveCommandExecutor


class RelativePathFollower(DriveCommandExecutor):
    """Follow waypoints expressed in the robot's local camera coordinate frame.

    Waypoints are replaced with latest-wins semantics. The follower estimates
    position from submitted normalized speed, steering angle, duration, and
    wheelbase; this is command-based odometry rather than wheel-encoder data.
    """

    def __init__(self, client: Client, speed: float, frame_height: int, wheelbase: float, min_confidence_before_refresh: float, refresh_hystersis: int, max_frames_before_refresh: int) -> None:
        """Initialize path-following parameters and refresh thresholds.

        :param client: The `Client` whose `drive_motors` the worker will call.
        :param speed: The speed at which to follow the path.
        :param frame_height: The height of the frame in the robot's local coordinate frame.
        :param wheelbase: The distance between the robot's wheels.
        :param min_confidence_before_refresh: The minimum confidence required before refreshing the path.
        :param refresh_hystersis: Number of consecutive low-confidence frames
            before requesting a path refresh. The misspelling is retained in
            the public parameter for compatibility.
        :param max_frames_before_refresh: The maximum number of frames to wait before refreshing the path.
        """
        super().__init__(client)
        self.speed: float = speed
        self.frame_height: int = frame_height
        self.wheelbase: float = wheelbase

        self._path_points_cache: np.ndarray[tuple[int, int], np.dtype[np.float64]] = np.array([
        ]).reshape(0, 2)
        self._dynamic_path_points: np.ndarray[tuple[int, int], np.dtype[np.float64]] = np.array([
        ]).reshape(0, 2)
        self._position_relative_to_start_of_path: tuple[float, float, float] = (
            0.0, 0.0, 0.0)

        self._latest_command: tuple[float, float, float] = (
            0.0, 0.0, 0.0)  # Speed angle duration
        self._last_odometry_update: float = time.perf_counter()

        self._request_refresh: asyncio.Event = asyncio.Event()
        self._refresh_hysteresis_counter: int = 0
        self.refresh_hysteresis_threshold: int = refresh_hystersis

        self.min_confidence_before_refresh: float = min_confidence_before_refresh
        self._frame_counter: int = 0
        self.max_frames_before_refresh: int = max_frames_before_refresh

    def _submit(self, speed: float, angle: float, duration: float) -> None:
        """
        Private alias for the parent class's submit method, which is overridden to prevent direct submission of drive commands during path following.
        """
        return super().submit(speed, angle, duration)

    def submit(self, speed: float, angle: float, duration: float) -> NoReturn:
        """Reject direct motor commands while path following is active.

        Path following must update its cached path and let its worker derive
        motor commands. Direct submission would bypass that state and make
        odometry inconsistent.

        :param speed: Motor speed that would have been submitted.
        :param angle: Steering angle that would have been submitted.
        :param duration: Command duration that would have been submitted.
        :raises NotImplementedError: Always, because callers must use
            :meth:`submit_path` for this executor.
        :returns: Never returns.
        :rtype: NoReturn
        """
        raise NotImplementedError(
            "Submitting individual drive commands during path following will lead to unpredictable behaviour. Use submit_path(), or a plain DriveCommandExecutor instead.")

    def _warp_path_points(self) -> None:
        """
        Warp the path points based on the robot's current position relative to the start of the path.
        This is done by translating by the accumulated position offset and then rotating into the
        robot's current frame using the accumulated yaw.
        """
        position = np.array(
            self._position_relative_to_start_of_path[:2], dtype=np.float64)
        yaw = float(self._position_relative_to_start_of_path[2])

        rotation = np.array(
            [
                [math.cos(-yaw), -math.sin(-yaw)],
                [math.sin(-yaw), math.cos(-yaw)],
            ],
            dtype=np.float64,
        )

        warped_points = (self._path_points_cache - position) @ rotation.T
        self._dynamic_path_points = warped_points[
            # Keep only points still in front of the robot in the current frame.
            # Camera coordinates are with y increasing downwards, so points in front of the robot have a y-coordinate less than or equal to the frame height.
            warped_points[:, 1] <= self.frame_height
        ]
        self._dynamic_path_points = self._dynamic_path_points[np.argsort(
            self._dynamic_path_points[:, 1])]

    def _update_odometry(self) -> None:
        """
        Update the robot's position relative to the start of the path based on the last command sent and the time elapsed since it was sent.
        """
        current_time = time.perf_counter()
        time_elapsed = current_time - self._last_odometry_update
        # Use the command duration if it's shorter than the time elapsed, since the robot would have stopped moving after the command duration.
        command_exec_time = min(self._latest_command[2], time_elapsed)

        # _latest_command[0] is normalized raw duty cycle but I cannot map it to a real speed within a reasonable time frame. Yes it's nonlinear
        r = self._latest_command[0] * command_exec_time
        theta: float = np.radians(
            self._latest_command[1] % 360)  # Absolute angle

        # convert to dx dy
        dx: float = r * np.cos(theta)
        dy: float = r * np.sin(theta)

        yaw = r / self.wheelbase * \
            np.tan(
                # Change in angle
                theta - self._position_relative_to_start_of_path[2])

        self._position_relative_to_start_of_path = (
            self._position_relative_to_start_of_path[0] + dx, self._position_relative_to_start_of_path[1] + dy, self._position_relative_to_start_of_path[2] + yaw)
        self._warp_path_points()
        self._last_odometry_update = current_time

    def _calc_next_command(self) -> tuple[float, float, float]:
        """Derive the next ``(speed, angle, duration)`` command.

        The highest-``y`` remaining waypoint is selected, with angle measured
        by ``atan2(y, x)`` in degrees. An empty path requests a refresh and
        returns a zero command.
        """
        if self._dynamic_path_points.shape[0] == 0:
            self._request_refresh.set()
            return (0.0, 0.0, 0.0)

        # always sorted by y, so the last point is the closest in front of the robot (since camera coordinates are with y increasing downwards)
        closest_point = self._dynamic_path_points[-1]

        # TODO: use numpy.gradient to calculate the angular velocity and use that to calculate a scaled speed based on the curvature of the path, instead of just using a constant speed.
        angle: float = np.degrees(np.arctan2(
            closest_point[1], closest_point[0]))
        distance: float = math.hypot(closest_point[0], closest_point[1])

        duration: float = max(
            distance / self.speed if self.speed > 0 else 0, 0.1)

        if 1 - abs(self._position_relative_to_start_of_path[2] - angle) / 180 < self.min_confidence_before_refresh:
            self._refresh_hysteresis_counter += 1
            if self._refresh_hysteresis_counter >= self.refresh_hysteresis_threshold:
                # continue to follow the path until a new path is submitted or the robot reaches the end of the path to avoid jittering when the path is not updated frequently enough.
                self._request_refresh.set()
        else:
            self._refresh_hysteresis_counter = 0

        return (self.speed, angle, duration)

    def submit_path(self, path_points: np.ndarray[tuple[int, int], np.dtype[np.float64]]) -> asyncio.Event:
        """Replace the active path with an ``(N, 2)`` floating-point array.

        Points are copied, sorted by increasing ``y``, and interpreted relative
        to the robot pose at submission time. The returned event is cleared for
        the new path and set when the path is exhausted or a refresh is needed.
        """
        self._path_points_cache = path_points.copy()[np.argsort(
            path_points[:, 1])]  # Sort by y-coordinate (increasing downwards)
        self._request_refresh.clear()
        self._wakeup.set()  # Wake up the worker to process the new path
        return self._request_refresh

    def tick(self) -> None:
        """Update refresh counters and submit the command for the next tick.

        Call this once per vision/control frame while a path is active. It can
        set the returned :meth:`submit_path` event when the refresh limit is
        reached.
        """
        self._frame_counter += 1
        if self._frame_counter >= self.max_frames_before_refresh:
            self._request_refresh.set()
            self._frame_counter = 0

        self._submit(*self._calc_next_command())

    async def _worker(self) -> NoReturn:
        """Background coroutine that consumes drive commands sequentially.

        Waits on :attr:`_wakeup`, pops the latest pending command, and
        awaits :meth:`Client.drive_motors`. Runs until cancelled.
        """
        # It's better to have the odometry update and _latest_command update in the worker, so if commands are submitted faster than they can be executed
        # the odometry will still be updated based on the last command executed, instead of the last command submitted, which may not have been executed yet.
        # This also reduces the delay between the odometry update and the command execution, which is important for accurate odometry.
        # Additionally, there is a significant accuracy increase since the dt of worker is likely much smaller than the dt of the main loop, so the odometry update will be more accurate.
        while True:
            await self._wakeup.wait()
            self._wakeup.clear()

            self._update_odometry()

            command: tuple[float, float, float] | None = self._pending
            self._pending = None
            if command is None:
                continue

            # Might seem redundant with pending, but this cannot be None,
            # and is used for odometry updates and calculating the next command, so it must always be the latest command processed by the worker.
            self._latest_command = command

            try:
                speed, angle, duration = command
                await self._client.drive_motors(speed, int(angle), duration)
            except Exception as e:
                logger.error(f"Drive command {command} failed: {e}")
