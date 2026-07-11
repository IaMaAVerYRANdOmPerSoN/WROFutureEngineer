from piclient.core.lib import export, Config

from argparse import ArgumentParser, Namespace
import dataclasses
from typing import Any
from collections.abc import Generator


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
    def __init__(
        self,
        root: Config,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.root = root
        super().__init__(*args, **kwargs)
        for k, v in _walk_config(root):
            self.add_argument(f"--{k}", help=f"Default: {v}")

    def parse_args( # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        args: Any = None,
        namespace: Namespace | None = None,
        **kwargs: Any,
    ) -> Namespace:
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
