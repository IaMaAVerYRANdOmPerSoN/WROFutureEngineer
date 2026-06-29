from collections.abc import Callable

from piclient.core.lib import GLOBAL_CONFIG, export
from .argument_parser import TypedArgumentParser
import ast

import numpy as np

_piclient_argument_parser = TypedArgumentParser(GLOBAL_CONFIG())

# Primitives
_piclient_argument_parser.register_constructor(int, int)
_piclient_argument_parser.register_constructor(float, float)
_piclient_argument_parser.register_constructor(str, str)

_piclient_argument_parser.register_constructor(dict, ast.literal_eval)
_piclient_argument_parser.register_constructor(tuple, ast.literal_eval)

# ndarrays
def _make_ndarray_constructor(dtype: type[np.uint8 | np.uint16 | np.uint32 | np.uint64 | np.float32 | np.float64]) -> Callable[[str], np.ndarray]:
    def f(raw: str) -> np.ndarray: return np.array(ast.literal_eval(raw), dtype=dtype)
    return f

for dt in (np.uint8, np.uint16, np.uint32, np.uint64, np.float32, np.float64):
    _piclient_argument_parser.register_constructor(
        np.ndarray[tuple[int, ...], np.dtype[dt]],
        _make_ndarray_constructor(dt),
    )

@export
def PICLIENT_ARGUMENT_PARSER() -> TypedArgumentParser:
    return _piclient_argument_parser