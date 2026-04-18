## Verdict: APPROVE

The plan is the smallest correct change that delivers the three-way split with real Tach enforcement.
It catches a stale-inventory landmine (the deleted `tool_approval.py` API), declines a tempting non-bug (`emit_custom_event`), and limits exception sprawl to two named items.
The shape matches the proven Tier-1 recipe (knowledge / memory / matrix), only adapted for a domain that is being SPLIT into three sub-facades rather than exposed as one.
Bias toward approval per the prompt — there is one architectural call (`plugin_identity` placement) I would have made differently, but the planner's choice is defensible and not worth blocking on.

## Architectural findings (with concrete reasoning, not gut feel)

1. **Three-way cleavage is the right shape.** Catalog (declarative metadata) / runtime (execution envelope) / extensions (loaders that mutate catalog) maps cleanly onto the lifecycle: define a tool → load tools into the registry → execute tools. Cross-domain callers actually break along these lines today (`mcp/manager.py` consumes catalog only; `bot.py` / `ai.py` / `streaming.py` consume runtime context + events; `orchestrator.py` consumes extension loaders). No symbol stood out as miscategorized to me.

2. **`plugin_identity.py` → extensions is the weakest call in the plan, but not a blocker.** `validate_plugin_name` is called from `runtime_context.py:24,504` (runtime) AND `plugins.py:18,401` (extensions) AND `hooks/context.py:10,59` (cross-domain). Putting it in extensions creates a new `runtime → extensions` sub-domain edge that did not exist before. The conceptually cleaner direction is the opposite — extensions builds on top of runtime, not the other way around. I would have pushed `plugin_identity.py` into `runtime` (its load-bearing caller is `get_plugin_state_root`, which computes durable storage paths — a runtime concern). The plan's justification ("canonical plugin identity policy shared by plugin loading and plugin-emitted events") prioritizes the plugin-loader caller; mine prioritizes execution-time path resolution. Both are defensible, neither blocks the seam. **No rework demanded.** If the gates surface this as a concrete Tach edge problem, flip it; otherwise leave it.

3. **`dependencies.py` → runtime is correct.** Its API (`auto_install_tool_extra`, `ensure_optional_deps`, `ensure_tool_deps`) is invoked at execution time by API endpoints and by `tools/python.py` to satisfy import-time availability. It is not declarative metadata. It does not load extensions. Runtime is the right home.

4. **Flat facade modules over subpackages is the right call here.** Subpackages would mean physically moving `metadata.py`, `worker_routing.py`, `runtime_context.py`, `sandbox_proxy.py`, `plugins.py`, `skills.py`, `tool_hooks.py` etc. into new directories. That is exactly the file-splitting work that ARCH-B-tools.md §"OUT of scope" forbids. Flat re-export modules deliver Tach-enforceable seams at `mindroom.tool_system.{catalog,runtime,extensions}` without any directory churn, matching Tier-1's pattern (memory, knowledge, matrix all used flat `__init__.py` re-exports).

5. **`emit_custom_event` "no fix" disposition is correct.** Verified against `src/mindroom/hooks/execution.py:174-192`: `_bind_hook_context()` builds `replacement_kwargs = {"plugin_name": hook.plugin_name, ...}` and calls `replace(context, **replacement_kwargs)` BEFORE the callback ever sees the context. The `plugin_name=""` at the emit site (`runtime_context.py:535`) is therefore overwritten with the *target hook's* plugin identity per invocation. Emitter identity survives in `source_plugin=plugin_name` (line 546). The probe outcome is sound — there is no lost identity, only a placeholder that gets overwritten. This is not the ≤5-line fix case.

6. **Special-tool dedup helper signature: `list[str]` is the right return type.** Both call sites (`agents.get_agent_toolkit_names()` line 567, `dynamic_toolkits._inject_special_tool_configs()` line 234) operate on names for the de-dup membership check today. Returning `ResolvedToolConfig` would force `agents.py` to either import `ResolvedToolConfig` and project `.name` out, or have two helpers. The wrapper at the dynamic-toolkits site is a one-liner (`ResolvedToolConfig(name=name, tool_config_overrides={})`). Names is the lowest common denominator for the dedup contract, and the plan's choice keeps `agents.py` free of an extra type import.

7. **`_TOOL_REGISTRY` transitional re-export is acceptable.** ARCH-B-tools.md §35 explicitly marks "MCP get a real public registry interface vs reading `_TOOL_REGISTRY`" as out of scope, and Bas's voice note in ARCH-000.md decision log reaffirms anti-scope-creep. Forcing a new MCP registry API in this issue would be exactly the over-reach Hard Rule #6 forbids. Leak via named transitional symbol with a comment is the correct disposition; flag for a follow-up issue if anyone pushes back.

8. **`_Plugin` and `_MODULE_IMPORT_CACHE` Tach exceptions are unavoidable within scope.** Re-exporting `_Plugin` would turn a private dataclass into typed public API across `agents.py`/`hooks/registry.py`. Re-exporting `_MODULE_IMPORT_CACHE` / `_ModuleCacheEntry` would expose loader internals just so `metadata.py` can snapshot them for transactional plugin restore. Both routes widen the public surface in exchange for cleaner Tach output — wrong tradeoff for boundary work. The prompt's "prefer Tach exception over type-surface churn" rule applies directly. Two named exceptions, each with a one-line comment, is the correct floor.

9. **Implementation order (facades → cross-subdomain imports → Tach interfaces → cross-domain migration → dedup + Agno comment) is sound.** The critical ordering constraint is that `[[interfaces]]` enforcement (step 3) cannot land green until cross-subdomain imports are routed through facades (step 2). Plan respects this. The only concrete risk is that step 3 surfaces a forgotten cross-subdomain import, requiring a partial re-do of step 2 — but that is the gate-driven feedback loop and not avoidable a priori.

10. **`mcp/toolkit.py` going under the extensions facade is fine.** It is a re-export only; the file stays in `mindroom/mcp/`. The new edge is `mindroom.tool_system.extensions → mindroom.mcp.toolkit`, which already exists today via direct callers in `orchestrator.py` and `mcp/registry.py`. No new cross-domain coupling is introduced; the seam just centralizes the existing one. Minor ownership ambiguity (extensions claims a symbol that physically lives in `mindroom/mcp/`) is a pragmatic price for not moving the file.

## Items I checked and confirmed sound

- Stale-inventory catch on `tool_approval.py` and the entire approval-store API — confirmed missing from the live tree on `arch-b-tools` worktree at `08c3f88b6`. Not reintroducing was the right call.
- Symbol counts (catalog 31, runtime 70, extensions 22) tally with what I cross-checked against ARCH-A §2 caller lists.
- `same-domain tool author modules` (`src/mindroom/tools/*.py`) staying on direct `metadata.py` imports — correct, they are catalog *authors*, not catalog *consumers*; routing 100+ leaf modules through the facade would be noise per Hard Rule #6.
- Agno monkey-patch comment text and placement in `tool_hooks.py` — correct per ARCH-A §8 disposition.
- `__init__.py` exposing only `["catalog", "extensions", "runtime"]` (no flat re-export of common symbols) — correct; this is a SPLIT, not a wrap, so forcing sub-facade choice on cross-domain callers is the architectural intent.

## Out-of-scope reviewer temptations I am NOT raising (demonstrate Hard Rule #6 awareness)

- `metadata.py` (1386 LOC), `worker_routing.py` (715 LOC), and `sandbox_proxy.py` (733 LOC) are huge — but ARCH-B-tools.md §"OUT of scope" explicitly forbids splitting them in this issue. Surface to Bas BEFORE doing it is the prescribed path.
- Inventory-counter caller migration: I did not re-run the import grep myself to verify every entry in §"Caller migration list" is exhaustive; the plan asserts these and that is what gates and `tach check` will verify in P3.
- I am not demanding a real MCP registry public interface, even though `_TOOL_REGISTRY` leaking transitionally is ugly — explicitly out of scope per Bas.
- I am not flagging `runtime_context.emit_custom_event` `plugin_name=""` as a bug — the planner's probe outcome is correct, and pursuing it further would be defensive-hardening for a non-failure.
- I did not raise potential subtle issues with `ensure_tool_registry_loaded` having deferred imports into `extensions` (`load_plugins`) and `mcp` — these are existing, deferred, intentional cycle-breakers; no observed failure mode, no scope claim.
- I am not asking for the `_TOOL_REGISTRY` callers to be migrated to a public accessor — that is the explicit MCP-refactor follow-up.
- I am not asking for documentation polish, type-annotation tightening, or docstring additions on untouched modules in this PR.
