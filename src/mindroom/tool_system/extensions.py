"""Public extensions facade for plugin, skill, toolkit, and MCP helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mindroom.mcp.toolkit import MindRoomMCPToolkit, bind_mcp_server_manager, require_mcp_server_manager
from mindroom.tool_system.dynamic_toolkits import (
    DynamicToolkitConflictError,
    DynamicToolkitSelection,
    get_loaded_toolkits_for_session,
    merge_runtime_tool_configs,
    resolve_dynamic_toolkit_selection,
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

if TYPE_CHECKING:
    from mindroom.config.main import Config


def resolve_special_tool_names(
    agent_name: str,
    config: Config,
    delegation_depth: int,
    enable_dynamic_tools_manager: bool,
) -> list[str]:
    """Resolve the ordered special-case tool names for one agent runtime."""
    agent_config = config.get_agent(agent_name)
    tool_names: list[str] = []

    if agent_config.delegate_to:
        from mindroom.custom_tools.delegate import MAX_DELEGATION_DEPTH  # noqa: PLC0415

        if delegation_depth < MAX_DELEGATION_DEPTH:
            tool_names.append("delegate")

    allow_self_config = (
        agent_config.allow_self_config
        if agent_config.allow_self_config is not None
        else config.defaults.allow_self_config
    )
    if allow_self_config:
        tool_names.append("self_config")

    if enable_dynamic_tools_manager and agent_config.allowed_toolkits:
        tool_names.append("dynamic_tools")

    return tool_names


__all__ = [
    "PluginValidationError",
    "load_plugins",
    "build_agent_skills",
    "clear_skill_cache",
    "get_skill_snapshot",
    "get_user_skills_dir",
    "list_skill_listings",
    "resolve_skill_command_spec",
    "resolve_skill_listing",
    "skill_can_edit",
    "DynamicToolkitConflictError",
    "DynamicToolkitSelection",
    "get_loaded_toolkits_for_session",
    "merge_runtime_tool_configs",
    "resolve_dynamic_toolkit_selection",
    "save_loaded_toolkits_for_session",
    "MindRoomMCPToolkit",
    "bind_mcp_server_manager",
    "require_mcp_server_manager",
    "resolve_special_tool_names",
]
