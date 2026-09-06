"""Predicates used to select Obstacle Challenge state transitions.

Each predicate receives the current vision sample, state, target, and lap count
and returns whether its destination state is eligible.
"""

from typing import Literal

from piclient.core.vision import WallsAndObstacles
from piclient.core.lib import TransitionManager, GLOBAL_CONFIG
from piclient.core.lib import export

ChallengeState = Literal[
    "obstacle_avoidance",
    "straight",
    "turn",
    "parallel_park"
]

type Target = tuple[int, int] | None
type LapCount = int

TypedTransitionManager = TransitionManager[
    [
        WallsAndObstacles,
        ChallengeState,
        Target,
        LapCount
    ],
    ChallengeState
]


def is_avoiding_obstacle(walls_and_obstacles: WallsAndObstacles) -> bool:
    """Return whether the most recent vision sample indicates obstacle avoidance is active.

    This helper is used by the challenge state machine to decide if the robot is
    currently avoiding a detected obstacle in the path ahead. The result is
    computed from the obstacle payload in the latest :class:`WallsAndObstacles`
    sample rather than from the current state label.

    :param walls_and_obstacles: The latest :class:`WallsAndObstacles` sample
        produced by the vision pipeline, including obstacle and wall geometry.
    :returns: ``True`` when an obstacle is present, otherwise ``False``.
    :rtype: bool
    """
    return walls_and_obstacles.obstacles is not None


def is_straight(walls_and_obstacles: WallsAndObstacles) -> bool:
    """Return whether the current wall geometry suggests the robot is in a straight segment.

    The decision uses the center wall fill ratio from the current vision frame. A
    low ratio indicates the corridor is open and the robot can continue straight,
    while a larger ratio indicates that a turn or corner is being approached.

    :param walls_and_obstacles: The most recent :class:`WallsAndObstacles`
        data containing the center-wall fill information.
    :returns: ``True`` when the center wall fill is below the configured straight
        threshold, otherwise ``False``.
    :rtype: bool
    """
    return walls_and_obstacles.walls.center <= GLOBAL_CONFIG().SharedChallengeConfig.CENTER_FILL_THRESHOLD


def is_turn(walls_and_obstacles: WallsAndObstacles) -> bool:
    """Return whether the center wall fill indicates a turn.

    No time or cooldown state is consulted; hysteresis and priorities are
    applied by :class:`TransitionManager`.

    :param walls_and_obstacles: The latest :class:`WallsAndObstacles` sample
        used to evaluate the corridor geometry.
    :returns: ``True`` only when the robot is not in a straight corridor, otherwise
        ``False``.
    :rtype: bool
    """
    return not is_straight(walls_and_obstacles)


@export
def should_avoid_obstacle(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: Target,
    lap_count: LapCount,
) -> bool:
    """Decide whether the robot should transition into obstacle avoidance.

    This rule is triggered when a visible target is present while the robot is in
    a turn or while it is driving straight but the wall geometry does not yet
    indicate a valid turn. It is the decision point that moves the challenge from
    normal wall-following into the obstacle-avoidance state.

    :param walls_and_obstacles: The latest :class:`WallsAndObstacles` sample
        containing the wall and obstacle geometry used to evaluate the state.
    :param state: The active challenge state, such as ``"straight"`` or
        ``"turn"``.
    :param target: Detector output for the visible obstacle target, or
        ``None`` when no target is currently visible.
    :param lap_count: The number of laps completed; this parameter is unused by
        this rule.
    :returns: ``True`` when obstacle avoidance should be selected, otherwise
        ``False``.
    :rtype: bool
    """
    del lap_count, walls_and_obstacles
    return target is not None and state in {"straight", "turn"}


@export
def should_straight(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: Target,
    lap_count: LapCount,
) -> bool:
    """Check whether the robot should return to the straight-driving state.

    The rule allows the robot to resume regular wall-following once an obstacle
    is cleared and no turn is active. It is primarily used after obstacle
    avoidance or during a turn when the wall geometry is clear.

    :param walls_and_obstacles: The most recent :class:`WallsAndObstacles`
        measurement containing wall and obstacle data.
    :param state: The current state of the challenge state machine.
    :param target: The current target coordinates, or ``None`` when no obstacle
        target is visible.
    :param lap_count: The number of laps completed; this parameter is unused by
        this rule.
    :returns: ``True`` when the robot should drive straight again, otherwise
        ``False``.
    :rtype: bool
    """
    del lap_count
    return state in {"obstacle_avoidance", "turn"} and target is None and not is_turn(walls_and_obstacles)


@export
def should_turn(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: Target,
    lap_count: LapCount,
) -> bool:
    """Decide whether the wall geometry requires a turn transition.

    This predicate is used when the robot should leave the straight path and
    begin following corner geometry. Sustained conditions are handled by the
    transition manager's hysteresis.

    :param walls_and_obstacles: The current :class:`WallsAndObstacles` sample.
    :param state: The active challenge state.
    :param target: Target coordinates from the vision system, or ``None`` when no target is visible.
    :param lap_count: The number of laps completed; this parameter is unused.
    :returns: ``True`` when the robot should transition into the turn state,
        otherwise ``False``.
    :rtype: bool
    """
    del lap_count
    return state in {"straight", "obstacle_avoidance"} and is_turn(walls_and_obstacles) and not target


@export
def should_parallel_park(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: Target,
    lap_count: LapCount,
) -> bool:
    """Determine whether the robot should enter the parallel parking state.

    This rule becomes eligible after at least three laps when a closer parking
    marker exists below the configured entry threshold. It accepts the normal
    driving states and does not use *target*.

    :param walls_and_obstacles: The latest :class:`WallsAndObstacles` sample
        containing wall and obstacle geometry.
    :param state: The current challenge state, such as ``"straight"`` or
        ``"turn"``.
    :param target: Detector output for the visible obstacle target, or
        ``None`` when no target is currently visible.
    :param lap_count: The number of laps completed
    :returns: ``True`` when parallel parking should be selected, otherwise
        ``False``.
    :rtype: bool
    """
    del target
    return lap_count >= 3 and walls_and_obstacles.parking_lot.closer is not None and state in {"straight", "turn", "obstacle_avoidance"} and walls_and_obstacles.parking_lot.closer.y_centroid > GLOBAL_CONFIG().ParallelParkingConfig.MIN_ENTRY_Y
