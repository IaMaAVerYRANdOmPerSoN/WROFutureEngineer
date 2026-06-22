import sys


def export(function_or_class):
    """Use a decorator to avoid retyping function/class names.

    * Based on an idea by Duncan Booth:
      http://groups.google.com/group/comp.lang.python/msg/11cbb03e09611b8a
    * Improved via a suggestion by Dave Angel:
      http://groups.google.com/group/comp.lang.python/msg/3d400fb22d8a42e1
    """
    mod = sys.modules[function_or_class.__module__]
    if hasattr(mod, '__all__'):
        name = function_or_class.__name__
        all_ = mod.__all__
        if name not in all_:
            all_.append(name)
    else:
        setattr(mod, '__all__', [function_or_class.__name__])
    return function_or_class


def export_globals():
    """Add every public name in the *caller's* namespace to its ``__all__`` (excluding leading underscores).

    Call this at the end of an ``__init__.py`` to auto-populate ``__all__``
    from all the names that were imported or defined in that file.
    """
    caller = sys._getframe(1)
    caller_globals = caller.f_globals
    mod = sys.modules[caller_globals["__name__"]]
    for name in tuple(caller_globals):
        if name.startswith("_") or "export_globals" in name:
            continue
        if hasattr(mod, '__all__'):
            all_ = mod.__all__
            if name not in all_:
                all_.append(name)
        else:
            setattr(mod, '__all__', [name])
