# IMPLEMENTATION_PLAN — ARCH-B-4

## Scope guard

This plan is Phase 0 only.
No code changes beyond this file are part of this commit.
Hard Rule #6 applies to every later implementation choice.
I am treating same-domain `src/mindroom/tools/*.py` registration modules as in-domain catalog authors, not cross-domain callers, so they are excluded from the caller-migration list below.
This revision addresses the Round 1 Codex critique directly and leaves `PLAN_CRITIQUE_CODEX.md` plus `PLAN_CRITIQUE_CLAUDE.md` in the tree as the audit trail.

## Reality check against the live tree

The Phase A report and ARCH-B prompt still mention `src/mindroom/tool_approval.py`, `initialize_approval_store`, `shutdown_approval_store`, `get_approval_store`, `ApprovalDecision`, `ApprovalManager`, `PendingApproval`, `ToolApprovalScriptError`, and `evaluate_tool_approval`.
Those symbols do not exist anywhere in this worktree on `arch-b-tools` as of 2026-04-18.
I am therefore planning the split against the live tree, not the stale approval inventory.
If DevAgent expected the older approval-store code to still exist, that mismatch needs confirmation before Phase 1, because reintroducing a removed approval subsystem would be net-new scope.

`src/mindroom/tool_system/dependencies.py` is still live and still has production callers.
It is omitted from the ARCH-B runtime symbol list, but it cannot stay orphaned outside the three-way split.
I am assigning `dependencies.py` to `mindroom.tool_system.runtime` because it is execution-time operational behavior, not declarative catalog state or extension loading.

`src/mindroom/tool_system/plugin_identity.py` is also still live.
I am assigning `validate_plugin_name()` to `mindroom.tool_system.runtime`, not `extensions`.
Reasoning: `runtime_context.get_plugin_state_root()` is the load-bearing caller, and this removes the one avoidable runtime -> extensions edge that Claude flagged.

`src/mindroom/api/sandbox_worker_prep.py` already uses `from mindroom.tool_system import sandbox_proxy`.
It is not a direct-symbol `sandbox_proxy.py` migration item, although it may still get a small alias cleanup later to satisfy the new runtime facade boundary.

## Facade layout decision

Recommendation: use three new flat facade modules, not three new subpackages.
Create `src/mindroom/tool_system/catalog.py`, `src/mindroom/tool_system/runtime.py`, and `src/mindroom/tool_system/extensions.py`.
Update `src/mindroom/tool_system/__init__.py` to re-export only those three facade modules.
Reasoning: this is the smallest correct change, matches Hard Rule #6, avoids directory churn, avoids pretending we are splitting the large existing files, and still gives Tach concrete package-level seams at `mindroom.tool_system.catalog`, `mindroom.tool_system.runtime`, and `mindroom.tool_system.extensions`.

`mindroom.tool_system.__all__` should be `["catalog", "extensions", "runtime"]`.
Cross-domain callers should prefer named sub-facades.
Top-level `mindroom.tool_system` remains only a namespace convenience for module-object imports such as `from mindroom.tool_system import runtime as tool_runtime`.

## Facade exports

### `mindroom.tool_system.catalog`

Core cross-domain catalog exports from `src/mindroom/tool_system/metadata.py` are `ConfigField`, `SetupType`, `TOOL_METADATA`, `_TOOL_REGISTRY`, `ToolAuthoredOverrideValidator`, `ToolCategory`, `ToolConfigOverrideError`, `ToolInitOverrideError`, `ToolMetadata`, `ToolMetadataValidationError`, `ToolStatus`, `ToolValidationInfo`, `apply_authored_overrides`, `authored_tool_overrides_to_runtime`, `default_worker_routed_tools`, `deserialize_tool_validation_snapshot`, `ensure_tool_registry_loaded`, `export_tools_metadata`, `get_tool_by_name`, `normalize_authored_tool_overrides`, `resolved_tool_metadata_for_runtime`, `resolved_tool_validation_snapshot_for_runtime`, `sanitize_tool_init_overrides`, `serialize_tool_validation_snapshot`, and `validate_authored_tool_entry_overrides`.

`_TOOL_REGISTRY` remains a deliberate transitional export for `mindroom.mcp.{manager,registry}` and private-registry tests only.
I am not inventing a new MCP registry API in this issue because ARCH-B-tools.md explicitly marks that out of scope.

The catalog facade also grows one small documented plugin lifecycle subset for `extensions.plugins`.
That subset is `synchronize_plugin_tools`, `capture_tool_registry_snapshot`, `restore_tool_registry_snapshot`, `locked_tool_registry_state`, `clear_plugin_tool_registrations`, `snapshot_plugin_tool_registrations`, `restore_plugin_tool_registrations`, and `scoped_plugin_registration_owner`.

The public alias names above intentionally drop leading underscores where the current `metadata.py` helpers are private-looking.
Phase 1 will rename only the `extensions.plugins` imports to those public alias names.
The current underscored implementations can stay in `metadata.py` for now.

### `mindroom.tool_system.runtime`

From `src/mindroom/tool_system/dependencies.py`: `auto_install_enabled`, `auto_install_tool_extra`, `check_deps_installed`, `ensure_optional_deps`, `ensure_tool_deps`, and `install_command_for_current_python`.

From `src/mindroom/tool_system/runtime_context.py`: `LiveToolDispatchContext`, `ToolDispatchContext`, `ToolRuntimeContext`, `ToolRuntimeHookBindings`, `ToolRuntimeSupport`, `append_tool_runtime_attachment_id`, `attachment_id_available_in_tool_runtime_context`, `build_scheduling_runtime_from_tool_runtime_context`, `emit_custom_event`, `get_plugin_state_root`, `get_tool_runtime_context`, `list_tool_runtime_attachment_ids`, `resolve_current_session_id`, `resolve_tool_runtime_hook_bindings`, `runtime_context_from_dispatch_context`, and `tool_runtime_context`.

From `src/mindroom/tool_system/plugin_identity.py`: `validate_plugin_name`.

From `src/mindroom/tool_system/worker_routing.py`: `ResolvedWorkerTarget`, `ToolExecutionIdentity`, `WorkerScope`, `active_tool_execution_identity`, `agent_state_root_path`, `agent_workspace_relative_path`, `agent_workspace_root_path`, `build_tool_execution_identity`, `build_worker_target_from_runtime_env`, `get_tool_execution_identity`, `local_shared_credential_allowlist`, `private_instance_scope_root_path`, `require_worker_key_for_scope`, `resolve_agent_owned_path`, `resolve_agent_state_storage_path`, `resolve_unscoped_worker_key`, `resolve_worker_execution_scope`, `resolve_worker_key`, `resolve_worker_target`, `resolved_worker_key_scope`, `requires_shared_only_integration_scope`, `run_with_tool_execution_identity`, `service_uses_local_shared_credentials`, `shared_storage_root`, `stream_with_tool_execution_identity`, `supports_tool_name_for_worker_scope`, `tool_execution_identity`, `unsupported_shared_only_integration_message`, `unsupported_shared_only_integration_names`, `visible_state_roots_for_worker_key`, `worker_dir_name`, `worker_root_path`, and `worker_scope_allows_shared_only_integrations`.

From `src/mindroom/tool_system/tool_hooks.py`: `build_tool_hook_bridge` and `prepend_tool_hook_bridge`.

From `src/mindroom/tool_system/events.py`: `StructuredStreamChunk`, `ToolTraceEntry`, `build_tool_trace_content`, `complete_pending_tool_block`, `extract_tool_completed_info`, `format_tool_combined`, `format_tool_completed_event`, and `format_tool_started_event`.

From `src/mindroom/tool_system/sandbox_proxy.py`: `maybe_wrap_toolkit_for_sandbox_proxy`, `sandbox_proxy_config`, and `to_json_compatible`.

`maybe_wrap_toolkit_for_sandbox_proxy`, `check_deps_installed`, and `supports_tool_name_for_worker_scope` stay exported even though they are not broad cross-domain API because `metadata.py` currently needs them across the catalog/runtime boundary.
Keeping those helpers behind `mindroom.tool_system.runtime` is smaller than widening the implementation diff with new wrapper layers.

`tool_failures.py` stays runtime-internal in Phase 1.
`tool_hooks.py` can keep its same-subdomain direct import of `record_tool_failure`.

### `mindroom.tool_system.extensions`

From `src/mindroom/tool_system/plugins.py`: `PluginValidationError` and `load_plugins`.

From `src/mindroom/tool_system/skills.py`: `build_agent_skills`, `clear_skill_cache`, `get_skill_snapshot`, `get_user_skills_dir`, `list_skill_listings`, `resolve_skill_command_spec`, `resolve_skill_listing`, and `skill_can_edit`.

From `src/mindroom/tool_system/dynamic_toolkits.py`: `DynamicToolkitConflictError`, `DynamicToolkitSelection`, `get_loaded_toolkits_for_session`, `merge_runtime_tool_configs`, `resolve_dynamic_toolkit_selection`, and `save_loaded_toolkits_for_session`.

From `src/mindroom/mcp/toolkit.py`: `MindRoomMCPToolkit`, `bind_mcp_server_manager`, and `require_mcp_server_manager`.

New export to add in `src/mindroom/tool_system/extensions.py`: `resolve_special_tool_names`.

`resolve_special_tool_names()` is the new de-dup helper described below.

## Explicit dispositions for the critique findings

### [H1] Missing runtime facade export

`service_uses_local_shared_credentials` is added to the runtime facade.
`src/mindroom/api/credentials.py` is a genuine cross-domain runtime caller, so I am not taking a Tach exception there.

### [H2] `plugins.py` private imports from `metadata.py`

I am not leaving those eight symbols as direct `extensions -> metadata.py` imports.
They become a documented catalog-side plugin lifecycle subset instead.

`synchronize_plugin_tools`: export from `mindroom.tool_system.catalog` with the same public name.
`_capture_tool_registry_snapshot`: expose via `mindroom.tool_system.catalog.capture_tool_registry_snapshot`.
`_restore_tool_registry_snapshot`: expose via `mindroom.tool_system.catalog.restore_tool_registry_snapshot`.
`locked_tool_registry_state`: export from `mindroom.tool_system.catalog` with the same public name.
`clear_plugin_tool_registrations`: export from `mindroom.tool_system.catalog` with the same public name.
`snapshot_plugin_tool_registrations`: export from `mindroom.tool_system.catalog` with the same public name.
`restore_plugin_tool_registrations`: export from `mindroom.tool_system.catalog` with the same public name.
`_scoped_plugin_registration_owner`: expose via `mindroom.tool_system.catalog.scoped_plugin_registration_owner`.

`src/mindroom/tool_system/plugins.py` will stop importing those symbols from `metadata.py` directly.
It will import only the catalog lifecycle subset from `mindroom.tool_system.catalog`.

`plugins._MODULE_IMPORT_CACHE` remains the one planned direct catalog <-> extensions exception in Phase 1.
I am not widening the public surface to include `_MODULE_IMPORT_CACHE` or `_ModuleCacheEntry`.

### [M3] Trim the wider-than-necessary facade exports

`register_tool_with_metadata`: remove from the catalog facade.
It stays on `metadata.py` as same-domain tool-authoring API for `src/mindroom/tools/**` and test-generated synthetic tool modules, covered by one Tach allowlist or exception rather than a public facade export.

`register_builtin_tool_metadata`: remove from the catalog facade.
It stays on `metadata.py` for the same tool-authoring reason as above.

`ToolManagedInitArg`: remove from the catalog facade.
It stays on `metadata.py` for same-domain tool authors and tests that validate authoring behavior.

`ToolExecutionTarget`: remove from the catalog facade.
It stays on `metadata.py` for same-domain tool authors and tests that validate authoring behavior.

`AUTHORED_OVERRIDE_INHERIT`: remove from the catalog facade.
It has no non-test cross-domain consumer on the live tree, so tests keep their direct import via a targeted Tach exception.

`validate_authored_overrides`: remove from the catalog facade.
It has no non-test cross-domain consumer on the live tree, so tests keep their direct import via a targeted Tach exception.

`build_tool_failure_record`: remove from the runtime facade.
It has no production cross-domain caller on the live tree, so tests keep their direct import via a targeted Tach exception.

`record_tool_failure`: remove from the runtime facade.
`tool_hooks.py` keeps its same-subdomain direct import, and tests keep their direct import via a targeted Tach exception.

`SandboxProxyConfig`: remove from the runtime facade.
It has no production cross-domain caller on the live tree, so tests keep their direct import via a targeted Tach exception.

This keeps the facade focused on real cross-domain production seams instead of tool-authoring helpers, private runtime plumbing, or test-only utilities.

### [M4] `api/sandbox_worker_prep.py` classification

`src/mindroom/api/sandbox_worker_prep.py` is dropped from the direct `sandbox_proxy.py -> runtime` migration list because it already uses the package-namespace form `from mindroom.tool_system import sandbox_proxy`.
That callsite is acknowledged separately here because it may still need a small alias cleanup to `from mindroom.tool_system.runtime import sandbox_proxy_config` once Tach starts enforcing exclusive implementation boundaries.
The important correction is that it is not a direct-symbol import migration item today.

### Claude nit: `plugin_identity` placement

I am taking Claude's suggestion.
`validate_plugin_name` moves to the runtime facade.
That gives `runtime_context.get_plugin_state_root()` a same-layer public home and eliminates one unnecessary runtime -> extensions edge.

## Internal exceptions I am planning to keep

`src/mindroom/tool_system/metadata.py` currently snapshots and restores `plugins._MODULE_IMPORT_CACHE`.
Exporting `_MODULE_IMPORT_CACHE` or `_ModuleCacheEntry` through a facade would turn pure loader internals into public API.
Plan: keep that one direct internal dependency and cover it with a targeted Tach exception plus a one-line comment.

`src/mindroom/agents.py` and `src/mindroom/hooks/registry.py` currently type against `plugins._Plugin`.
Plan: keep those as targeted Tach exceptions rather than re-export `_Plugin`.
That matches the prompt's "prefer a Tach exception over type-surface churn for private internals" rule.

`src/mindroom/tools/**` remain direct `metadata.py` authoring callers for `register_tool_with_metadata`, `register_builtin_tool_metadata`, `ToolManagedInitArg`, and `ToolExecutionTarget`.
That is an intentional same-domain allowlist, not a migration miss.

Tests that import `AUTHORED_OVERRIDE_INHERIT`, `validate_authored_overrides`, `build_tool_failure_record`, `record_tool_failure`, `SandboxProxyConfig`, `_TOOL_REGISTRY`, `_Plugin`, `_get_plugin_skill_roots`, `_SkillCommandDispatch`, `_SkillCommandSpec`, or underscored `events.py` constants stay on targeted Tach exceptions instead of widening the public seam.

## Caller migration list

### `mindroom.tool_system.metadata` -> `mindroom.tool_system.catalog`

Migrate these production callers to `from mindroom.tool_system.catalog import ...`: `src/mindroom/agents.py`, `src/mindroom/api/sandbox_runner.py`, `src/mindroom/api/tools.py`, `src/mindroom/config/agent.py`, `src/mindroom/config/main.py`, `src/mindroom/custom_tools/config_manager.py`, `src/mindroom/custom_tools/self_config.py`, `src/mindroom/mcp/manager.py`, `src/mindroom/mcp/registry.py`, `src/mindroom/tool_system/plugins.py`, and `src/mindroom/workers/runtime.py`.

`src/mindroom/tool_system/plugins.py` is in that list specifically for the plugin lifecycle subset named above.
Keep same-domain tool author modules on `metadata.py` for now: `src/mindroom/tools/__init__.py` and `src/mindroom/tools/*.py`.
Those modules live inside the tool domain and moving all of them to the facade would be noise, not boundary work.

### `mindroom.tool_system.dependencies` -> `mindroom.tool_system.runtime`

Migrate these production callers to `from mindroom.tool_system.runtime import ...`: `src/mindroom/api/google_integration.py`, `src/mindroom/api/integrations.py`, `src/mindroom/api/main.py`, `src/mindroom/custom_tools/_google_oauth.py`, `src/mindroom/embeddings.py`, and `src/mindroom/tools/python.py`.

### `mindroom.tool_system.runtime_context` -> `mindroom.tool_system.runtime`

Migrate these production callers to `from mindroom.tool_system.runtime import ...`: `src/mindroom/agents.py`, `src/mindroom/bot.py`, `src/mindroom/commands/handler.py`, `src/mindroom/custom_tools/attachment_helpers.py`, `src/mindroom/custom_tools/attachments.py`, `src/mindroom/custom_tools/browser.py`, `src/mindroom/custom_tools/compact_context.py`, `src/mindroom/custom_tools/delegate.py`, `src/mindroom/custom_tools/matrix_api.py`, `src/mindroom/custom_tools/matrix_helpers.py`, `src/mindroom/custom_tools/matrix_message.py`, `src/mindroom/custom_tools/matrix_room.py`, `src/mindroom/custom_tools/scheduler.py`, `src/mindroom/custom_tools/subagents.py`, `src/mindroom/custom_tools/thread_summary.py`, `src/mindroom/custom_tools/thread_tags.py`, `src/mindroom/history/compaction.py`, `src/mindroom/message_target.py`, `src/mindroom/response_lifecycle.py`, `src/mindroom/response_runner.py`, `src/mindroom/turn_controller.py`, and `src/mindroom/turn_store.py`.

### `mindroom.tool_system.worker_routing` -> `mindroom.tool_system.runtime`

Migrate these production callers to `from mindroom.tool_system.runtime import ...`: `src/mindroom/agent_policy.py`, `src/mindroom/agents.py`, `src/mindroom/ai.py`, `src/mindroom/api/credentials.py`, `src/mindroom/api/google_integration.py`, `src/mindroom/api/integrations.py`, `src/mindroom/api/openai_compat.py`, `src/mindroom/api/sandbox_exec.py`, `src/mindroom/api/sandbox_runner.py`, `src/mindroom/api/tools.py`, `src/mindroom/bot.py`, `src/mindroom/cli/config.py`, `src/mindroom/commands/handler.py`, `src/mindroom/config/agent.py`, `src/mindroom/config/main.py`, `src/mindroom/config/models.py`, `src/mindroom/conversation_state_writer.py`, `src/mindroom/credentials.py`, `src/mindroom/custom_tools/_google_oauth.py`, `src/mindroom/custom_tools/compact_context.py`, `src/mindroom/custom_tools/delegate.py`, `src/mindroom/custom_tools/gmail.py`, `src/mindroom/custom_tools/google_calendar.py`, `src/mindroom/custom_tools/google_sheets.py`, `src/mindroom/custom_tools/homeassistant.py`, `src/mindroom/custom_tools/memory.py`, `src/mindroom/history/runtime.py`, `src/mindroom/knowledge/shared_managers.py`, `src/mindroom/knowledge/utils.py`, `src/mindroom/matrix/invited_rooms_store.py`, `src/mindroom/memory/_file_backend.py`, `src/mindroom/memory/_mem0_backend.py`, `src/mindroom/memory/_policy.py`, `src/mindroom/memory/auto_flush.py`, `src/mindroom/memory/functions.py`, `src/mindroom/post_response_effects.py`, `src/mindroom/response_runner.py`, `src/mindroom/runtime_resolution.py`, `src/mindroom/teams.py`, `src/mindroom/workers/backends/kubernetes.py`, `src/mindroom/workers/backends/kubernetes_resources.py`, `src/mindroom/workers/backends/local.py`, and `src/mindroom/workers/backends/static_runner.py`.

That list is intentionally still broad because `worker_routing.py` is the largest live cross-domain leak.
The concrete correction from Round 1 is that the runtime facade now includes `service_uses_local_shared_credentials`, so `src/mindroom/api/credentials.py` has a real target export.

### `mindroom.tool_system.events` -> `mindroom.tool_system.runtime`

Migrate these production callers to `from mindroom.tool_system.runtime import ...`: `src/mindroom/ai.py`, `src/mindroom/api/openai_compat.py`, `src/mindroom/bot.py`, `src/mindroom/delivery_gateway.py`, `src/mindroom/hooks/context.py`, `src/mindroom/matrix/mentions.py`, `src/mindroom/streaming.py`, and `src/mindroom/teams.py`.

### `mindroom.tool_system.tool_hooks` -> `mindroom.tool_system.runtime`

Migrate these production callers to `from mindroom.tool_system.runtime import ...`: `src/mindroom/agents.py`.

### `mindroom.tool_system.sandbox_proxy` -> `mindroom.tool_system.runtime`

Migrate these direct symbol-import callers to `from mindroom.tool_system.runtime import ...` or `from mindroom.tool_system import runtime as tool_runtime`: `src/mindroom/api/main.py`, `src/mindroom/api/sandbox_runner.py`, and `src/mindroom/api/workers.py`.

`src/mindroom/api/sandbox_worker_prep.py` is intentionally not in that direct-import list because it already uses the package-namespace form.
If Tach still flags that namespace-path dependency after the facade lands, normalize that one callsite to `from mindroom.tool_system.runtime import sandbox_proxy_config`.

### `mindroom.tool_system.dynamic_toolkits` -> `mindroom.tool_system.extensions`

Migrate these production callers to `from mindroom.tool_system.extensions import ...`: `src/mindroom/agents.py` and `src/mindroom/custom_tools/dynamic_tools.py`.

### `mindroom.tool_system.plugins` -> `mindroom.tool_system.extensions`

Migrate these production callers to `from mindroom.tool_system.extensions import ...` or `from mindroom.tool_system import extensions as tool_extensions`: `src/mindroom/agents.py`, `src/mindroom/api/sandbox_runner.py`, `src/mindroom/config/main.py`, and `src/mindroom/orchestrator.py`.

Keep `src/mindroom/agents.py` and `src/mindroom/hooks/registry.py` on `_Plugin` via targeted Tach exception.

### `mindroom.tool_system.skills` -> `mindroom.tool_system.extensions`

Migrate these production callers to `from mindroom.tool_system.extensions import ...`: `src/mindroom/agents.py`, `src/mindroom/api/skills.py`, `src/mindroom/commands/handler.py`, and `src/mindroom/orchestrator.py`.

### `mindroom.mcp.toolkit` -> `mindroom.tool_system.extensions`

Migrate these production callers to `from mindroom.tool_system.extensions import ...`: `src/mindroom/mcp/registry.py` and `src/mindroom/orchestrator.py`.

### `mindroom.tool_system.plugin_identity` -> `mindroom.tool_system.runtime`

Migrate this production cross-domain caller to `from mindroom.tool_system.runtime import validate_plugin_name`: `src/mindroom/hooks/context.py`.

Inside `tool_system`, `src/mindroom/tool_system/plugins.py` should also stop importing `validate_plugin_name` directly from `plugin_identity.py`.
It should import that helper from the runtime facade for the same reason.

## Agno monkey-patch isolation strategy

The monkey-patch stays in `src/mindroom/tool_system/tool_hooks.py`.
No module outside `mindroom.tool_system.runtime` should reference `FunctionCall._build_nested_execution_chain_async`, `_ORIGINAL_BUILD_NESTED_EXECUTION_CHAIN_ASYNC`, or `_AGNO_ASYNC_TOOL_HOOK_CHAIN_PATCHED`.
Add the required comment immediately above `_ORIGINAL_BUILD_NESTED_EXECUTION_CHAIN_ASYNC = FunctionCall._build_nested_execution_chain_async`.
Comment text: `Agno upgrade landmine — see ARCH-000.md for context.`

## Special-tool injection de-dup

Current duplication is real.
`src/mindroom/tool_system/dynamic_toolkits.py:_inject_special_tool_configs()` and `src/mindroom/agents.py:get_agent_toolkit_names()` both decide whether to add `delegate`, `self_config`, and `dynamic_tools`, and both import `MAX_DELEGATION_DEPTH`.

Plan: add `resolve_special_tool_names()` to `src/mindroom/tool_system/extensions.py`.
Inputs: `agent_name`, `config`, `delegation_depth`, and `enable_dynamic_tools_manager`.
Output: ordered `list[str]` containing zero or more of `delegate`, `self_config`, and `dynamic_tools`.
`agents.get_agent_toolkit_names()` will append the returned names to the configured tool list.
`dynamic_toolkits._inject_special_tool_configs()` will call the same helper and convert each returned name into `ResolvedToolConfig(name=<tool_name>, tool_config_overrides={})` only when missing.
The helper will own the single import of `mindroom.custom_tools.delegate.MAX_DELEGATION_DEPTH`.

## `emit_custom_event()` probe outcome

Probe result: no code change is warranted for the `plugin_name=""` field on the current branch.
Reason: `src/mindroom/hooks/execution.py:_bind_hook_context()` overwrites `plugin_name` and `settings` per target hook before callback execution, while `CustomEventContext.source_plugin` is the emitter identity that survives to the callback.
That makes `plugin_name=""` in `emit_custom_event()` an intentional placeholder, not a lost source identity.
This is therefore not the ≤5-line fix case.
I am not flagging it as a blocker because the live behavior is internally consistent.

## Tach shape

Add `[[modules]]` entries for `mindroom.tool_system.catalog`, `mindroom.tool_system.runtime`, `mindroom.tool_system.extensions`, and `mindroom.tool_system`.
Add one public `[[interfaces]]` block for each facade module.
Add `exclusive = true` `[[interfaces]]` blocks for the runtime and extensions implementation modules that should be hidden behind those facades.
Do not split the existing large implementation files.

Do not make `metadata.py` facade-exclusive in an absolute sense in Phase 1.
Cross-domain catalog consumers should move to `mindroom.tool_system.catalog`.
Same-domain catalog authors in `src/mindroom/tools/**` can keep direct `metadata.py` imports for the authoring helpers that are intentionally staying off the facade.

I expect a small set of explicit Tach exceptions or allowlists to remain.
They are `_Plugin` in `agents.py` and `hooks/registry.py`, the `metadata.py -> plugins._MODULE_IMPORT_CACHE` coupling, the same-domain `src/mindroom/tools/**` authoring imports listed above, and whichever private test-only imports still exist after the production migrations land.

## Test strategy

Do not edit tests unless they fail after the seam lands.
If a failing test uses only public symbols, migrate it to the new facade path with the smallest possible edit.
If a failing test imports private internals such as `_TOOL_REGISTRY`, `_Plugin`, `_get_plugin_skill_roots`, `_SkillCommandDispatch`, `_SkillCommandSpec`, or underscored `events.py` constants, prefer a Tach exception with a one-line comment over widening the seam or rewriting the test.

Planned gates under `nix-shell` after Phase 1 are the ones already specified in ARCH-B-tools.md.
Run `uv run tach check`.
Run `uv run pytest tests/test_tool*.py tests/test_plugins*.py tests/test_dynamic_toolkits*.py -x -n 0 --no-cov -v`.
Run `pre-commit run --all-files`.
Add import smoke for `mindroom.tool_system`, `mindroom.tool_system.catalog`, `mindroom.tool_system.runtime`, and `mindroom.tool_system.extensions`.

## Implementation order for Phase 1

1. Add `catalog.py`, `runtime.py`, `extensions.py`, and update `tool_system/__init__.py`.
2. Put the revised public seam in place immediately by adding the catalog plugin lifecycle subset, the runtime `validate_plugin_name` export, and the runtime `service_uses_local_shared_credentials` export.
3. Update internal cross-subdomain imports that can move cleanly to the new facades, especially `tool_system/plugins.py`.
4. Migrate the production cross-domain callers listed above.
5. Add the three Tach interfaces plus the minimal exclusive implementation-module interfaces plus the targeted allowlists or exceptions called out above.
6. Land the special-tool de-dup helper and the Agno patch comment.
7. Only then touch tests or add any further targeted Tach exceptions if the gates demand it.
