"""
Argument parser that automatically generates arguments from a nested dataclass configuration object.
"""

from typing import Any

import dataclasses
from argparse import ArgumentParser, Namespace
from collections.abc import Generator

from piclient.core.lib import export, Config


def _walk_config(
    obj: object,
    prefix: str = "",
) -> Generator[tuple[str, object], None, None]:
    """Yield ``(dotted_key, value)`` pairs for every leaf in a nested dataclass tree."""
    for key, value in vars(obj).items():
        if key.startswith("_"):
            continue
        full_key = f"{prefix}.{key}" if prefix else key
        if dataclasses.is_dataclass(value):
            yield from _walk_config(value, full_key)
        else:
            yield full_key, value


@export
class TypedArgumentParser(ArgumentParser):
    """Argument parser that derives options from nested configuration fields.

    Every leaf discovered by :func:`_walk_config` becomes a dotted command-line
    option. Parsed strings are converted using the root configuration's type
    annotations and written back into that configuration.

    :ivar root: Configuration object whose fields define the options.
    """
    def __init__(
        self,
        root: Config,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the parser and register one option per config leaf.

        :param root: Nested configuration object to expose.
        :param args: Positional arguments forwarded to
            :class:`argparse.ArgumentParser`.
        :param kwargs: Keyword arguments forwarded to the parent parser.
        :returns: ``None``.
        :rtype: None
        """
        self.root = root
        super().__init__(*args, **kwargs)
        for k, v in _walk_config(root):
            self.add_argument(f"--{k}", help=f"Default: {v}")

    def parse_args(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        args: Any = None,
        namespace: Namespace | None = None,
        **kwargs: Any,
    ) -> Namespace:
        """Parse options, cast supplied values, and update the root config.

        Unspecified options are removed from the returned namespace. Supplied
        values are converted using :meth:`Config.get_caster`.

        :param args: Arguments to parse, or ``None`` for ``sys.argv``.
        :param namespace: Optional namespace to populate.
        :param kwargs: Additional parser compatibility arguments.
        :returns: Namespace containing only explicitly supplied options.
        :rtype: argparse.Namespace
        """
        parsed: Namespace = super().parse_args(args, namespace) # pyright: ignore[reportAssignmentType]

        for attr, raw_value in list(vars(parsed).items()):
            if raw_value is None:
                delattr(parsed, attr)  # Remove so getattr(..., default) works
                continue

            type_ = self.root.get_annotation(attr)
            caster = type(self.root).get_caster(type_)
            setattr(parsed, attr, caster(raw_value))
            self.root.set_nested_attr(path=attr, value=getattr(parsed, attr))

        return parsed
