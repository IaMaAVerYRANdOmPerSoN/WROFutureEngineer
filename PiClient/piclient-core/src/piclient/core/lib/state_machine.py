"""
State machine implementation for managing the robot's states and transitions.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, ParamSpec, Self

from .exporter import export
from .transition_manager import TransitionManager, P, T
from ..interface import DriveCommandExecutor

HandlerParams = ParamSpec("HandlerParams")

PExternal = ParamSpec("PExternal")
PTransition = ParamSpec("PTransition")


@export
class StateMachine(Generic[HandlerParams, PExternal, PTransition, T], ABC):
    """Abstract asynchronous state machine for robot control behavior.

    The machine stores the active state, delegates transition decisions to a
    :class:`TransitionManager`, and delegates drive output to a
    :class:`DriveCommandExecutor`. Subclasses provide state-specific actions.

    :ivar current_state: State identifier currently being executed.
    :ivar transition_manager: Object that evaluates state transitions.
    :ivar drive_command_executor: Asynchronous drive command sink.
    """

    def __init__(self, initial_state: T, transition_manager: TransitionManager[P, T], drive_command_executor: DriveCommandExecutor) -> None:
        """Initialize the state machine.

        :param initial_state: The initial state of the state machine.
        :param transition_manager: An instance of TransitionManager to handle state transitions.
        :param drive_command_executor: An instance of DriveCommandExecutor to execute drive commands.
        """
        self.current_state = initial_state
        self.transition_manager = transition_manager
        self.drive_command_executor = drive_command_executor
        self._setup_complete = False

    async def __aenter__(self) -> Self:
        """Enter the asynchronous context manager."""
        await self.drive_command_executor.__aenter__()
        return self

    async def __aexit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: object) -> None:
        """Exit the asynchronous context manager."""
        await self.drive_command_executor.__aexit__(exc_type, exc_value, traceback)

    def update(self, *args: PExternal.args, **kwargs: PExternal.kwargs,) -> None:
        """Update the state machine by checking for possible transitions.

        Subclasses may transform the external arguments in
        :meth:`_populate_transition_params` before the transition manager sees
        them. If a determinant wins, its destination becomes
        :attr:`current_state`.

        :param args: External positional inputs for transition evaluation.
        :param kwargs: External keyword inputs for transition evaluation.
        """
        new_args, new_kwargs = self._populate_transition_params(
            *args, **kwargs)
        next_state = self.transition_manager.check_transitions(
            *new_args, **new_kwargs)
        if next_state is not None:
            self.current_state = next_state

    def _populate_transition_params(self, *args: PExternal.args, **kwargs: PExternal.kwargs) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Populate the parameters for the transition determinants.

        :param args: Positional arguments to pass to the transition determinants.
        :param kwargs: Keyword arguments to pass to the transition determinants.
        :return: A tuple containing the positional and keyword arguments for the transition determinants.
        """
        return args, kwargs

    @abstractmethod
    def handle_state_actions(self, *args: HandlerParams.args, **kwargs: HandlerParams.kwargs) -> bool:
        """Handle actions based on the current state.

        Subclasses should override this method to define actions for each state.
        The base body only runs :meth:`setup` once and stores its result; it
        does not itself return that result despite the boolean annotation.

        :param args: Positional arguments to pass to the state action handlers.
        :param kwargs: Keyword arguments to pass to the state action handlers.
        :return: True if the state machine has completed its setup and is ready to proceed, False otherwise.
        """
        if not self._setup_complete:
            self._setup_complete = self.setup(*args, **kwargs)

    def setup(self, *args: HandlerParams.args, **kwargs: HandlerParams.kwargs) -> bool:
        """Perform one-time preparation before normal state actions.

        Override this method for startup maneuvers such as leaving a parking
        lot. The default implementation does nothing and returns ``True``;
        subclasses can return ``False`` until their preparation is complete.

        :param args: Setup inputs supplied by the caller.
        :param kwargs: Setup keyword inputs supplied by the caller.
        :returns: Whether setup is complete.
        :rtype: bool
        """
        # TODO: May want to overhaul this, we are getting closer to a state machine which can contain multiple sub-state machines.
        # I'm not sure how to implement this yet, but it would be nice to have a state machine which can contain other state machines as states.
        # Perhaps we just use the name of the StateMachine instance as the state name, and then we can have a transition manager which can handle
        # nested transitions.
        # Default implementation does nothing and returns True, indicating that the setup is complete.
        return True
