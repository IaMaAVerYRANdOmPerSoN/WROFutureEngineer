"""
Transition manager class for the PiClient. This class is responsible for managing the transitions between different states in a Finite State Machine (FSM)

It takes callables in it's constructor for each "transition determinant" (i.e. a function that returns a boolean indicating whether the transition should occur),
and a hysteresis value for each transition. The transition manager will only trigger a transition if the determinant returns True for a number of consecutive calls equal to the hysteresis value.
"""

from typing import ParamSpec, Generic, TypeVar, cast

from collections.abc import Callable, Sequence
from inspect import Signature, signature

from loguru import logger
from .exporter import export


# Generic for function signatures of transition determinants
P = ParamSpec("P")
T = TypeVar("T", bound=str)  # Typevar for state names


@export
class TransitionManager(Generic[P, T]):
    """Evaluate prioritized state transitions with configurable hysteresis.

    Each named determinant is called with only the arguments its signature can
    accept. A determinant must remain true for its hysteresis threshold before
    it can win, and the highest-priority eligible determinant supplies the next
    state.

    :ivar debug_entries: Latest threshold status for each determinant.
    """

    def __init__(self, *, hysteresis_values: Sequence[int], priorities: Sequence[int], **transition_determinants: Callable[P, bool]) -> None:
        """Initialise the transition manager.

        :param transitions_determinants: Callables that determine whether a transition should occur.
        :param hysteresis_values: Number of consecutive True calls required to trigger a transition for each determinant.
        :param priorities: Priorities for each transition determinant.
        """

        if len(transition_determinants) != len(hysteresis_values):
            raise ValueError(
                "Number of transition determinants must match number of hysteresis values.")
        if len(priorities) != len(transition_determinants):
            raise ValueError(
                "Number of priorities must match number of transition determinants.")

        if len(set(priorities)) != len(priorities):
            raise ValueError(
                "Priorities must be unique for each transition determinant.")

        if any(priority < 0 for priority in priorities):
            raise ValueError("Priorities must be non-negative integers.")
        if any(hysteresis < 0 for hysteresis in hysteresis_values):
            raise ValueError(
                "Hysteresis values must be non-negative integers.")

        self._hysteresis_values = cast(dict[T, int], {name: hysteresis for name, hysteresis in zip(
            transition_determinants.keys(), hysteresis_values)})
        self._priorities = cast(dict[T, int], {name: priority for name, priority in zip(
            transition_determinants.keys(), priorities)})
        self._hysteresis_counters = cast(
            dict[T, int], {name: 0 for name in transition_determinants.keys()})
        self._transition_determinants = cast(
            dict[T, Callable[P, bool]], transition_determinants)
        self._transition_signatures: list[Signature] = [
            signature(callback) for _, callback in transition_determinants.items()
        ]

        # For debugging purposes, to track the results of each transition determinant over time.
        self.debug_entries: dict[T, bool] = {
            name: False for name in self._transition_determinants.keys()}

    def check_transitions(self, *args: P.args, **kwargs: P.kwargs) -> T | None:
        """Check all transition determinants and update hysteresis counters.
        Automatically resets hysteresis counters when a transition occurs to avoid immediate re-triggering of the same transition.

        :param args: Arguments to pass to each transition determinant.
        :param kwargs: Keyword arguments to pass to each transition determinant.
        :returns: string indicating which state to transition to based on priority, or None if no transition should occur.
        """
        result = None
        incremented_states: list[T] = []
        priority = -1  # Initialize with a value lower than any possible priority
        for state_name, callback, signature in zip(self._transition_determinants.keys(), self._transition_determinants.values(), self._transition_signatures):
            # Filter args and kwargs based on the signature of the callback
            try:
                bound_args = signature.bind(*args, **kwargs)
                bound_args.apply_defaults()
            except TypeError as e:
                # Could be intentional, It's hard to expect them to all have the same signature, so we just skip it if it doesn't match.
                logger.warning(
                    f"Can't bind arguments to {getattr(callback, '__name__', state_name)}: {e}, skipping this transition determinant.")
                continue

            filtered_args = bound_args.args
            filtered_kwargs = bound_args.kwargs

            should_increment: bool = callback(
                *filtered_args, **filtered_kwargs)
            if should_increment:
                self._hysteresis_counters[state_name] += 1
                incremented_states.append(state_name)
            else:
                self._hysteresis_counters[state_name] = 0

            hysteresis_value = self._hysteresis_values[state_name]
            threshold_met = should_increment if hysteresis_value == 0 else self._hysteresis_counters[
                state_name] >= hysteresis_value

            if threshold_met:
                self.debug_entries[state_name] = True
                if self._priorities[state_name] > priority:
                    priority = self._priorities[state_name]
                    result = state_name
                    self._hysteresis_counters[state_name] = 0
            else:
                self.debug_entries[state_name] = False
        logger.debug(f"Transition check complete.", extra={
            "new_state": result,
            "selected_states": sorted([state for state, threshold_met in self.debug_entries.items() if threshold_met],
                                      key=lambda state: self._priorities[state], reverse=True),
            "incremented_states": incremented_states,
            "hysteresis_counters": self._hysteresis_counters,
        })

        if result is not None:
            # Reset all hysteresis counters to avoid immediate re-triggering of the same transition.
            self._reset_hysteresis()
        return result

    def _reset_hysteresis(self) -> None:
        """Reset all hysteresis counters to zero. Call this when a transition occurs to reset the state of the transition manager."""
        self._hysteresis_counters = {
            name: 0 for name in self._hysteresis_counters}
