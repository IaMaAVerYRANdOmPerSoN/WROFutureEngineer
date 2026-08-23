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

    async def __aenter__(self) -> Self:
        """Enter the asynchronous context manager."""
        await self.drive_command_executor.__aenter__()
        return self

    async def __aexit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: object) -> None:
        """Exit the asynchronous context manager."""
        await self.drive_command_executor.__aexit__(exc_type, exc_value, traceback)

    def update(self, *args: PExternal.args, **kwargs: PExternal.kwargs,) -> None:
        """Update the state machine by checking for possible transitions.

        :param args: Positional arguments used to determine the next state and update internals.
        :param kwargs: Same as args, but as keyword arguments.
        """
        new_args, new_kwargs = self._populate_transition_params(*args, **kwargs)
        next_state = self.transition_manager.check_transitions(*new_args, **new_kwargs)
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

        This method should be overridden in subclasses to define specific actions for each state.

        :param args: Positional arguments to pass to the state action handlers.
        :param kwargs: Keyword arguments to pass to the state action handlers.
        :return: True if the state machine has completed its setup and is ready to proceed, False otherwise.
        """
        if not self._setup_complete and not self.setup(*args, **kwargs):
            self._setup_complete = True
        else:
            return False

    def setup(self, *args: HandlerParams.args, **kwargs: HandlerParams.kwargs) -> bool:
        """
        Perform any necessary operations before the core loop starts. This method can be overridden in subclasses to provide custom setup logic.
        For example, a robot might need to exit a parking lot before starting the main loop. This method can be used to implement such behavior.
        :param args: Positional arguments to pass to the setup method.
        :param kwargs: Keyword arguments to pass to the setup method.
        :return: True if the setup is complete and the state machine is ready to proceed, False otherwise.
        """
        # TODO: May want to overhaul this, we are getting closer to a state machine which can contain multiple sub-state machines.
        # I'm not sure how to implement this yet, but it would be nice to have a state machine which can contain other state machines as states.
        # Perhaps we just use the name of the StateMachine instance as the state name, and then we can have a transition manager which can handle
        # nested transitions.
        return True  # Default implementation does nothing and returns True, indicating that the setup is complete.