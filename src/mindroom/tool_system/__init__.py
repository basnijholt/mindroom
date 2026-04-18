"""Public facade modules for MindRoom tool infrastructure."""

from __future__ import annotations

from importlib import import_module

__all__ = ["catalog", "extensions", "runtime"]

_MODULE_EXPORTS = {
    "catalog": "mindroom.tool_system.catalog",
    "extensions": "mindroom.tool_system.extensions",
    "runtime": "mindroom.tool_system.runtime",
}


def __getattr__(name: str) -> object:
    module_name = _MODULE_EXPORTS.get(name)
    if module_name is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    value = import_module(module_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
