import cv2
import asyncio
from utils.tools.base_tool import BaseTool
from src.controller import PD
from src.config import Config

class ControlTool(BaseTool):
    def __init__(self):
        super().__init__(name="control", description="View control status and diagnostics")
        self.open_challenge_pd_straight = PD(Config.OpenChallengeConfig.WALL_FOLLOW_KPKD)
        self.open_challenge_pd_turn = PD(Config.OpenChallengeConfig.CORNER_TURN_KPKD)
        self.obstacle_challenge_straight_pd = PD(Config.ObstacleChallengeConfig.WALL_FOLLOW_KPKD)
        self.obstacle_challenge_turn_pd = PD(Config.ObstacleChallengeConfig.CORNER_TURN_KPKD)
        self.obstacle_challenge_obstacle_pd = PD(Config.ObstacleChallengeConfig.OBSTACLE_AVOID_KPKD)


    def _draw(self, data, *args, **kwargs):
        # TODO: Add autual control ouputs and visualize robot path planning, offsets and target values, etc. instead of being a more annoying config file viewer
        cv2.putText(self.frame, "Control Tool - Diagnostics", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(self.frame, f"Open Challenge PD Straight: P={self.open_challenge_pd_straight.kp:.2f} D={self.open_challenge_pd_straight.kd:.2f}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(self.frame, f"Open Challenge PD Turn: P={self.open_challenge_pd_turn.kp:.2f} D={self.open_challenge_pd_turn.kd:.2f}", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(self.frame, f"Obstacle Challenge PD Straight: P={self.obstacle_challenge_straight_pd.kp:.2f} D={self.obstacle_challenge_straight_pd.kd:.2f}", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(self.frame, f"Obstacle Challenge PD Turn: P={self.obstacle_challenge_turn_pd.kp:.2f} D={self.obstacle_challenge_turn_pd.kd:.2f}", (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(self.frame, f"Obstacle Challenge PD Obstacle Avoidance: P={self.obstacle_challenge_obstacle_pd.kp:.2f} D={self.obstacle_challenge_obstacle_pd.kd:.2f}", (10, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.imshow("Control Diagnostics", self.frame)
