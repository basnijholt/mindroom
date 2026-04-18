"""Public extensions facade for plugin, skill, toolkit, and MCP helpers."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mindroom.mcp.toolkit import MindRoomMCPToolkit, bind_mcp_server_manager, require_mcp_server_manager
    from mindroom.tool_system.dynamic_toolkits import (
        DynamicToolkitConflictError,
        DynamicToolkitSelection,
        get_loaded_toolkits_for_session,
        merge_runtime_tool_configs,
        resolve_dynamic_toolkit_selection,
        resolve_special_tool_names,
        save_loaded_toolkits_for_session,
    )
    from mindroom.tool_system.plugins import PluginValidationError, load_plugins
    from mindroom.tool_system.skills import (
        build_agent_skills,
        clear_skill_cache,
        get_skill_snapshot,
        get_user_skills_dir,
        list_skill_listings,
        resolve_skill_command_spec,
        resolve_skill_listing,
        skill_can_edit,
    )

_EXPORT_MODULES = {
    "PluginValidationError": "mindroom.tool_system.plugins",
    "load_plugins": "mindroom.tool_system.plugins",
    "build_agent_skills": "mindroom.tool_system.skills",
    "clear_skill_cache": "mindroom.tool_system.skills",
    "get_skill_snapshot": "mindroom.tool_system.skills",
    "get_user_skills_dir": "mindroom.tool_system.skills",
    "list_skill_listings": "mindroom.tool_system.skills",
    "resolve_skill_command_spec": "mindroom.tool_system.skills",
    "resolve_skill_listing": "mindroom.tool_system.skills",
    "skill_can_edit": "mindroom.tool_system.skills",
    "DynamicToolkitConflictError": "mindroom.tool_system.dynamic_toolkits",
    "DynamicToolkitSelection": "mindroom.tool_system.dynamic_toolkits",
    "get_loaded_toolkits_for_session": "mindroom.tool_system.dynamic_toolkits",
    "merge_runtime_tool_configs": "mindroom.tool_system.dynamic_toolkits",
    "resolve_dynamic_toolkit_selection": "mindroom.tool_system.dynamic_toolkits",
    "save_loaded_toolkits_for_session": "mindroom.tool_system.dynamic_toolkits",
    "MindRoomMCPToolkit": "mindroom.mcp.toolkit",
    "bind_mcp_server_manager": "mindroom.mcp.toolkit",
    "require_mcp_server_manager": "mindroom.mcp.toolkit",
    "resolve_special_tool_names": "mindroom.tool_system.dynamic_toolkits",
}

__all__ = [
    "DynamicToolkitConflictError",
    "DynamicToolkitSelection",
    "MindRoomMCPToolkit",
    "PluginValidationError",
    "bind_mcp_server_manager",
    "build_agent_skills",
    "clear_skill_cache",
    "get_loaded_toolkits_for_session",
    "get_skill_snapshot",
    "get_user_skills_dir",
    "list_skill_listings",
    "load_plugins",
    "merge_runtime_tool_configs",
    "require_mcp_server_manager",
    "resolve_dynamic_toolkit_selection",
    "resolve_skill_command_spec",
    "resolve_skill_listing",
    "resolve_special_tool_names",
    "save_loaded_toolkits_for_session",
    "skill_can_edit",
]


def __getattr__(name: str) -> object:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
