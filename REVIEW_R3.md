## R3 Verdict: APPROVE

The three-way catalog / runtime / extensions seam is real, Tach-enforced where it matters, and follows Tier-1 conventions adapted for a domain that legitimately needs orthogonal sub-facades.
`tach check` passes on the worktree.
The implementation also clears the `_Plugin` Tach exception that the plan reserved as unavoidable — by introducing a `HookRegistryPlugin` Protocol in `src/mindroom/hooks/registry.py:22-28`, which is strictly stronger than the plan called for.
Findings below are minor / cleanup-tier, not blocker-tier.

## Architectural findings (concrete reasoning required)

1. **[Low] `tools/python.py` was on the migration list but never moved.**
   Plan §"`dependencies` -> `runtime`" line 189 lists `src/mindroom/tools/python.py` as a caller to migrate.
   `src/mindroom/tools/python.py:9` still reads `from mindroom.tool_system.dependencies import install_command_for_current_python`.
   Tach does not catch it because `mindroom.tools` is not in `[[modules]]`, so the `exclusive=true` interface on `mindroom.tool_system.dependencies` (tach.toml:914-925) does not bind for callers outside the declared module set.
   Concrete consequence: a future contributor copying `tools/python.py` for a new tool will copy the direct-internal pattern instead of the facade pattern.
   Fix is one line; mention so it doesn't drift.

2. **[Low] Stale `runtime_context` dep declarations in `tach.toml`.**
   `mindroom.bot` and `mindroom.commands.handler` were migrated off `tool_system.runtime_context` in commit d6a69a082 (`bot.py:56,143` now use `mindroom.tool_system.runtime`; `commands/handler.py:28` likewise), but tach.toml:235 and tach.toml:248 still declare `mindroom.tool_system.runtime_context` in their `depends_on` lists.
   Concrete consequence: the `[[interfaces]]` exclusive visibility of `runtime_context` (tach.toml:947-953) lists `bot` / `commands.handler` as still-eligible consumers via the dep declaration, weakening the architectural intent of "cross-domain callers go through the runtime facade."
   Drop the two stale entries.

3. **[Info] Audit-trail files are committed and will appear in the PR.**
   `IMPLEMENTATION_PLAN.md`, `PLAN_CRITIQUE_CODEX.md`, and `PLAN_CRITIQUE_CLAUDE.md` are tracked at the worktree root (committed in 08c3f88b6 / 2a730825f / 68de9f9d3 / 2249a5a73).
   The prompt's note "these will be excluded from the final PR per the established workflow" needs an explicit step — currently they are in the branch and would land in `git diff origin/main..HEAD`.
   Either drop the four commits before opening the PR or move the files under a path the PR strategy already excludes.

4. **[Info, no action] The declared dep graph in tach.toml has a 4-cycle.**
   `tool_system.metadata` → (`tool_system.extensions`, `tool_system.plugins`, `tool_system.runtime`); `tool_system.extensions` → `tool_system.plugins`; `tool_system.plugins` → `tool_system.catalog`; `tool_system.catalog` → `tool_system.metadata`.
   This is intentional and works only because the catalog/extensions edges are deferred (function-local) imports and the runtime/extensions facades use module-level `__getattr__` lazy resolution — at actual import time there is no cycle.
   Tach declares dep allowlists, not strict layering, so it accepts the configuration.
   Documenting in case a future reviewer reads the tach.toml top-down and asks "how is this not a cycle."

## Items checked and confirmed sound

- Three-way split enforcement: implementation-side modules (`metadata`, `runtime_context`, `worker_routing`, `events`, `tool_hooks`, `sandbox_proxy`, `dependencies`, `skills`, `dynamic_toolkits`, `mcp.toolkit`, `plugin_identity`) all have `exclusive = true` `[[interfaces]]` blocks restricting cross-domain consumers to the facades. A future contributor doing `from mindroom.tool_system.metadata import _TOOL_REGISTRY` from a non-catalog file will be blocked by Tach (tach.toml:737-775).
- `validate_plugin_name` runtime placement (Claude-nit acceptance): correctly exposed via `mindroom.tool_system.runtime` (runtime.py:111) and the `plugin_identity` interface visibility includes only `runtime` and `runtime_context` (tach.toml:955-959). No new runtime→extensions edge created.
- Public alias names for the 8 lifted plugin-lifecycle helpers (`synchronize_plugin_tools`, `capture_tool_registry_snapshot`, `restore_tool_registry_snapshot`, `locked_tool_registry_state`, `clear_plugin_tool_registrations`, `snapshot_plugin_tool_registrations`, `restore_plugin_tool_registrations`, `scoped_plugin_registration_owner`): all defined in `metadata.py:90-164` and aliased in commit d77c4ae95; consistent with codebase naming (verb_noun, no leading underscore, no leaked implementation language).
- `_Plugin` Tach exception is no longer needed at all — `HookRegistryPlugin` Protocol replaces it cleanly. `_Plugin` now appears only inside `tool_system/plugins.py` (verified via grep). This is a strictly stronger architectural outcome than the plan documented.
- Tier-1 consistency: facade `__init__.py` re-exports module-level facade names (matching memory/knowledge/matrix's "expose only the supported public surface" pattern). The deviation — three sub-facades instead of one — is justified by the orthogonal lifecycle stages (define / load / execute) and called out in the plan.
- ARCH-A §2 cross-domain caller migration: spot-checked `service_uses_local_shared_credentials` (now exported via `mindroom.tool_system.runtime`, runtime.py:134), `_TOOL_REGISTRY` MCP consumers (mcp/manager.py and mcp/registry.py both go through `mindroom.tool_system.catalog`), `sandbox_worker_prep.py` (now uses runtime facade per Codex M4), `bot.py` / `ai.py` / `streaming.py` / `orchestrator.py` (all go through facades, no direct `tool_system.<impl>` imports).
- `mcp/toolkit.py` extensions placement: the file stays in `mindroom/mcp/`, only the export route is centralized through `mindroom.tool_system.extensions`. New edge `extensions → mcp.toolkit` is correct because the toolkit is consumed by extension-tier callers (orchestrator startup, mcp/registry) and exposing it through the existing facade keeps cross-domain callers on one entry point.
- Recurring same-category issue scan across the 4 commits: none found. Each commit has a single clean responsibility (add facades / route internals / add tach interfaces / migrate callers). No repeated workaround pattern that would suggest an architectural smell.
- `[[interfaces]]` export-list width: every facade interface block matches its `__all__` 1:1 with no speculative widening. Internal `[[interfaces]]` blocks are tightly scoped via `exclusive = true` and per-module `visibility` lists — no broader-than-needed seam.
- Special-tool de-dup helper (`resolve_special_tool_names`): landed in `dynamic_toolkits.py`, exposed via extensions facade, called from both `agents.get_agent_toolkit_names` and `dynamic_toolkits._inject_special_tool_configs`. The `MAX_DELEGATION_DEPTH` import is centralized in the helper.

## Out of scope (not raised, Hard Rule #6 demonstration)

- Splitting `metadata.py` (1386 LOC), `worker_routing.py`, `runtime_context.py`, `sandbox_proxy.py`, or `plugins.py` into smaller files — explicitly out of scope per ARCH-B-tools.md.
- Replacing `_TOOL_REGISTRY` with a public MCP registry interface — explicitly out of scope per Bas's anti-scope-creep note in ARCH-000 and the plan.
- Reintroducing the removed `tool_approval.py` subsystem — would be net-new scope; planner correctly flagged the stale inventory.
- Tightening the cyclic-looking `tach.toml` dep graph by introducing a new boundary module — would require splitting catalog or extensions, which is out of scope.
- Speculative hardening around the Agno monkey-patch beyond the comment requirement.
- Adding type-annotation tightening or docstrings on untouched modules.
- Demanding the `mindroom.tools.*` authoring imports be routed through facades — these are intentional same-domain author callers, and routing 100+ leaf modules would be exactly the noise Hard Rule #6 forbids. (My `tools/python.py` finding above is narrowly about the one entry the plan itself listed for migration, not a broader push.)
