"""
State machine implementation for managing the robot's states and transitions.
"""

from typing import Any, Generic, ParamSpec, Self

from .exporter import export
from .transition_manager import TransitionManager, P, T
from ..interface import DriveCommandExecutor

HandlerParams = ParamSpec("HandlerParams")

PExternal = ParamSpec("PExternal")
PTransition = ParamSpec("PTransition")

@export
class StateMachine(Generic[HandlerParams, PExternal, PTransition, T]):
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

    def handle_state_actions(self, *args: HandlerParams.args, **kwargs: HandlerParams.kwargs) -> bool:
        """Handle actions based on the current state.

        This method should be overridden in subclasses to define specific actions for each state.

        :param args: Positional arguments to pass to the state action handlers.
        :param kwargs: Keyword arguments to pass to the state action handlers.
        """
        raise NotImplementedError(
            "Subclasses should implement this method to handle state-specific actions.")
