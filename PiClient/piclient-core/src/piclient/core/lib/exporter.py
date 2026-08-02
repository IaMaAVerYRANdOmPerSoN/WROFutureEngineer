"""
Exporter module for managing the `__all__` attribute of modules, packages, and subpackages.
This module provides the `export` decorator and the `export_globals` function to facilitate the automatic population of the `__all__` attribute, which defines the public API of a module.

(not really, becuase python doesn't have a concept of public/private, but it does make it easier to manage what gets imported with `from module import *`)
"""

from typing import Any, TypeVar

import inspect
import sys


_T = TypeVar("_T", bound=Any)


def export(obj: _T) -> _T:
    """Use a decorator to avoid retyping function/class names.

    * Based on an idea by Duncan Booth:
      http://groups.google.com/group/comp.lang.python/msg/11cbb03e09611b8a
    * Improved via a suggestion by Dave Angel:
      http://groups.google.com/group/comp.lang.python/msg/3d400fb22d8a42e1
    """
    mod = sys.modules[obj.__module__]
    if hasattr(mod, '__all__'):
        name: str = obj.__name__
        all_: list[str] = mod.__all__
        if name not in all_:
            all_.append(name)
    else:
        setattr(mod, '__all__', [obj.__name__])
    return obj


def export_globals() -> None:
    """Add every public name in the *caller's* namespace to its ``__all__`` (excluding leading underscores).

    Call this at the end of an ``__init__.py`` to auto-populate ``__all__``
    from all the names that were imported or defined in that file.
    """
    caller = inspect.currentframe()
    if caller is None or caller.f_back is None:
        return
    caller_globals: dict[str, Any] = caller.f_back.f_globals
    mod = sys.modules[caller_globals["__name__"]]
    for name in tuple(caller_globals):
        if name.startswith("_") or "export_globals" in name:
            continue
        if hasattr(mod, '__all__'):
            all_: list[str] = mod.__all__
            if name not in all_:
                all_.append(name)
        else:
            setattr(mod, '__all__', [name])
