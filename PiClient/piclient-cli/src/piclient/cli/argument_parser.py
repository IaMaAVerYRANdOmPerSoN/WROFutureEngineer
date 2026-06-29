from piclient.core.lib import export

from argparse import ArgumentParser, Namespace
from typing import Any, TypeVar, get_origin
from collections.abc import Callable
from annotationlib import get_annotations

_T = TypeVar("_T")

@export
class TypedArgumentParser(ArgumentParser):
    _constructors: dict[type[Any], Callable[[str], Any]]

    def __init__(
        self,
        root: object,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.root = root
        self._constructors = {}
        return super().__init__(*args, **kwargs)

    def register_constructor(self, type_: type[_T], constructor: Callable[[str], _T]) -> None:
        """Add a constructor for *type_* to the internal registry. the constructor must take a single string argument and return an object of type *_type.*"""
        self._constructors[type_] = constructor

    def _get_nested_type(self, dotted_path: str) -> type:
        """Get the type of ``root.a.b.c`` given ``dotted_path == 'a.b.c'``."""
        root: object = self.root
        *parents, leaf = dotted_path.split(".")

        for part in parents:
            root = getattr(root, part)

        res = getattr(root, leaf)

        annotations = get_annotations(type(root))
        return annotations.get(leaf, type(res))

    def parse_args(
        self,
        *args: Any,
        **kwargs: Any
    ) -> Namespace:
        namespace = super().parse_args(*args, **kwargs)

        for attr, raw_value in list(vars(namespace).items()):
            if raw_value is None:
                delattr(namespace, attr)  # Remove so getattr(..., default) works
                continue
            type_ = self._get_nested_type(attr)
            origin = get_origin(type_) or type_
            constructor: Callable[[str], Any] = self._constructors.get(type_) or self._constructors.get(origin, lambda x: x)
            setattr(namespace, attr, constructor(raw_value))

        return namespace
