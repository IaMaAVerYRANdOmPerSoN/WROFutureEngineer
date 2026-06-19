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