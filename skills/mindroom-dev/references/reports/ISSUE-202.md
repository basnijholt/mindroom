# ISSUE-202: Manual Compaction Should Run After The Reply That Requested It

Status: 🔍 APPROVAL PENDING — merged to local main as `2ee82e0a9`; awaiting Bas verification.
Base inspected: `origin/main` at `9d87c88f6` (`feat: save tool outputs to workspace files (ISSUE-200) (#729)`).
Date: 2026-04-25.

This report synthesizes the Codex and Claude plans plus both critiques. It is intentionally narrow: fix post-response handling of manual `compact_context()` requests, update wording, and add focused tests.

## Problem

When an agent calls `compact_context()` during a turn, compaction is deferred until the next user-triggered turn. The visible sequence is:

1. Turn N: the agent calls `compact_context()`, then finalizes its assistant reply.
2. No compaction notice appears after that reply.
3. The user sends another message.
4. Turn N+1 sends `Thinking...`, then foreground history preparation runs forced compaction and sends `Compacting history...`.

Expected behavior: for a successful visible turn, manual compaction should run immediately after the reply that requested it. Next-turn forced compaction remains a fallback only when the requesting turn fails, is cancelled, is suppressed, or otherwise does not reach successful post-response effects.

## Current Call Flow

`CompactContextTools.compact_context()` validates that destructive compaction is available, writes `HistoryScopeState(force_compact_before_next_run=True)` to scope metadata, and also writes a pending compaction scope key to Agno `run_context.session_state`.

The double write is still needed. A later Agno save from the same run can overwrite scope metadata with stale pre-tool state; the `session_state` marker lets `_prepare_scope_state_for_run()` recover that request on a later preparation pass.

After a successful response, `ResponseLifecycle.finalize()` calls `apply_post_response_effects()`, which dispatches post-response compaction checks. The shared helper `run_post_response_compaction_check()` currently reads persisted scope state directly and then returns early when `force_compact_before_next_run` is true. It also does not consume the Agno `session_state` fallback.

At the start of the next turn, `prepare_scope_history()` calls `_prepare_scope_state_for_run()`, which does consume the fallback and classifies the force flag as required foreground compaction. On Matrix, `ResponseRunner.run_cancellable_response()` sends `Thinking...` before the response task starts, so deferred foreground compaction appears after `Thinking...` on the next turn.

There is a second gate mismatch: `_post_response_compaction_checks_for_scope()` currently emits checks only when authored auto compaction is enabled. Manual compaction is valid when destructive compaction is available, even if authored auto compaction is disabled.

## Root Cause

The existing post-response hook is treated as auto/opportunistic only. Forced manual state is interpreted as work reserved for the next foreground preparation pass.

That was coherent for older "next reply" semantics, but it conflicts with the desired contract: the turn that requests manual compaction should pay the compaction cost immediately after its final visible reply succeeds.

## Final Decisions

- Clear the force flag on post-response manual compaction failure, matching foreground forced compaction. Do not retry that same failed post-response compaction on the next turn.
- Use the hard replay budget (`hard_replay_budget_tokens or replay_budget_tokens`) for forced manual post-response compaction. This matches foreground required compaction for lifecycle metadata and target-budget consistency. Forced all-visible first-pass selection still comes from the forced state passed into `compact_scope_history()`, not from the budget value itself.
- Broaden post-response check creation to all manual-capable destructive scopes, not only authored-auto scopes.
- Use `_prepare_scope_state_for_run()` in the post-response path so Agno `session_state` pending markers are consumed there too.
- Preserve the existing next-turn fallback for turns that fail, are cancelled, are suppressed, or never successfully deliver a final response.
- Update tool wording so it promises after-current-reply compaction with next-turn fallback if that cannot complete.

## Implementation Plan

### 1. Update `run_post_response_compaction_check()`

In `src/mindroom/history/runtime.py`:

- Replace the direct `read_scope_state()` with `_prepare_scope_state_for_run()` to consume the `session_state` fallback.
- Keep destructive compaction availability as a hard precondition for emitted post-response checks. This preserves the invariant that `_prepare_scope_state_for_run()` will not clear a force flag because destructive compaction is unavailable in this path.
- Remove the forced-state skip branch.
- Add a cheap return after state preparation when no force flag is present and authored auto compaction is disabled.
- Classify with `force_compact_before_next_run=state.force_compact_before_next_run`.
- Use lifecycle mode `"manual"` for forced state and `"auto"` otherwise. Let `CompactionOutcome.mode` continue to report success mode from `compact_scope_history()`.
- For forced state, use `execution_plan.hard_replay_budget_tokens or execution_plan.replay_budget_tokens` as `available_history_budget`. For ordinary auto checks, keep the current trigger replay budget.
- Pass the prepared forced state into `compact_scope_history()`. Existing compaction selection should remain unchanged: forced first pass selects all visible runs, and existing rewrite logic preserves the selected set through summary-budget-limited passes.
- On exception, emit failure with mode `"manual"` and clear the force flag/pending request, consistent with foreground forced compaction.

### 2. Broaden post-response check creation

In `_post_response_compaction_checks_for_scope()`:

- Remove the `authored_compaction_enabled` requirement.
- Keep the other gates: `session_id`, scope, destructive compaction availability, and summary input budget.

In the no-force/auto-disabled case, `run_post_response_compaction_check()` should return before token estimation or model loading. The expected extra cost is one state-preparation read after successful replies in destructive/manual-capable scopes with auto compaction disabled.

The Matrix lifecycle anchor should not change. `post_response_effects.py` already builds the compaction lifecycle with `reply_to_event_id=response_event_id`, so `Compacting history...` replies to the finalized assistant event rather than the original user event or a later placeholder.

### 3. Preserve fallback behavior

Keep `add_pending_force_compaction_scope()` and `consume_pending_force_compaction_scope()`.

Do not loosen the success gates in `apply_post_response_effects()`. If the response is not completed, is suppressed, or delivery fails before a final visible event, post-response compaction should not run and the existing next-turn foreground forced compaction path should remain the fallback.

### 4. Update wording

Update:

- `src/mindroom/tools/compact_context.py`
- `src/mindroom/custom_tools/compact_context.py`
- checked-in generated docs that expose the tool description

Recommended wording:

```text
Compaction will run after this reply is finalized. If that cannot complete, it will be attempted before the next reply.
```

Do not keep user-facing text that says the tool only schedules compaction for the next reply.

## Out Of Scope

- Changing Matrix `Thinking...` placeholder timing.
- Changing Matrix compaction notice wording.
- Refactoring lifecycle adapters or extracting a shared compaction executor.
- Renaming `force_compact_before_next_run` or changing storage schema.
- Removing the Agno `session_state` fallback.
- Changing `compact_scope_history()` selection or rewrite semantics beyond passing the prepared forced state into the existing path.

## Test Plan

Add or update focused tests in existing files:

1. `tests/test_agno_history.py`: post-response manual compaction when metadata force flag is set, authored auto compaction is disabled, and destructive compaction is available. Assert manual outcome/mode, compaction below the auto trigger threshold, and cleared markers after success.
2. `tests/test_agno_history.py`: post-response manual compaction when metadata lacks the force flag but `session.session_data["session_state"]` contains the pending compaction scope key. Assert the marker is consumed and compaction runs immediately.
3. `tests/test_agno_history.py`: forced post-response failure path. Inject a failure, assert lifecycle failure mode is manual, the already-finalized response is unaffected, and force/pending markers are cleared.
4. `tests/test_agno_history.py` or nearby runtime coverage: no-force auto-disabled check returns before token estimation/model loading.
5. `tests/test_compact_context.py`: update tool return-string assertions and preserve tests proving the force flag and pending marker are written.
6. `tests/test_compaction.py` or response lifecycle tests: assert the compaction lifecycle `reply_to_event_id` is the finalized assistant `response_event_id` and that response-event linkage is persisted before compaction starts.
7. `tests/test_openai_compat.py`: add completion-predicate gating coverage. Incomplete OpenAI streams must not consume the force marker; completed streams should consume it and invoke the shared post-response compaction helper.
8. Failed/cancelled-turn fallback if feasible: simulate a turn that calls `compact_context()` but does not reach successful post-response effects, then assert next-turn history preparation still runs foreground forced compaction.

Focused command:

```bash
uv run pytest -n 0 --no-cov \
  tests/test_compact_context.py \
  tests/test_compaction.py \
  tests/test_agno_history.py \
  tests/test_openai_compat.py
```

Use `nix-shell --run '...'` if the local environment requires it.

## Live-Test Plan

Use lab only; do not restart production `mindroom-chat.service`.

Success path:

- Configure a lab agent with `compact_context` and destructive compaction available.
- Build enough visible prior history to compact.
- Ask the agent to call `compact_context()` and finish a reply.
- Verify event order: finalized assistant reply, then `Compacting history...` as a reply to that finalized event, then the success/failure edit.
- Verify no extra user message is required, and the next user-triggered turn does not show stale compaction after `Thinking...`.
- Capture event ids, timestamps, logs, and persisted state proving the force flag and pending marker were cleared.

Fallback path if feasible:

- Simulate a failed or cancelled turn after the tool writes markers but before successful post-response effects.
- Verify the next turn still consumes the fallback and runs foreground forced compaction.

## Risks

- Clearing on post-response failure can lose a one-shot manual request after a transient summary-model failure. This is accepted for consistency with foreground forced compaction and to avoid repeated failing compaction notices on every subsequent turn.
- Broadened check creation adds one state read after successful replies in destructive/manual-capable scopes. The no-force/auto-disabled early return should keep this bounded.
- OpenAI and Matrix share the core helper, but their post-response completion gates differ. The OpenAI completion-predicate test is required so incomplete streams do not consume fallback markers early.

## Implementation Notes

- `prepare_history_for_run()` now records post-response checks for manual-capable scopes even when authored automatic compaction is disabled. The post-response runner returns before token estimation/model loading when there is no force marker and automatic compaction is disabled.
- `run_post_response_compaction_check()` now prepares scope state through the same force-marker path used by foreground history preparation, so both persisted metadata and Agno `session_state` pending markers can trigger immediate manual post-response compaction.
- Forced post-response runs are classified and reported as manual, use the hard replay budget when configured, and clear consumed force markers after compaction failure to match foreground forced semantics.
- Lifecycle coverage remains anchored to successful finalized responses: failed, cancelled, suppressed, or non-finalized response paths do not consume the force marker and keep the next-turn fallback.
- `compact_context()` user-facing text and generated tool/docs metadata now describe the after-current-reply behavior with next-reply fallback.

## Round 1 Follow-Up

R1 review found one convergent blocker: forced manual post-response compaction still returned early when the active runtime model had no replay budget (`compact_history_budget is None`), even though foreground forced compaction supports that state when an explicit compaction model has a `context_window` and summary budget.

Fix: the `compact_history_budget is None` guard now applies only to ordinary unforced auto post-response compaction. Forced manual post-response compaction proceeds with `available_history_budget=None`, matching foreground forced compaction.

Regression coverage: `test_run_post_response_compaction_check_uses_compaction_model_window_when_active_model_has_none` mirrors the foreground active-model-None case through `run_post_response_compaction_check()`. It asserts immediate manual post-response compaction, force-marker clearing, and `outcome.history_budget_tokens is None`.

## Test Results

- `nix-shell --run 'uv sync --group dev --all-extras'`
- `nix-shell --run 'uv run pytest -n 0 --no-cov tests/test_agno_history.py -k "post_response_compaction_check or post_response_check"'` passed: 10 passed, 95 deselected.
- `nix-shell --run 'uv run pytest -n 0 --no-cov tests/test_compact_context.py tests/test_compaction.py tests/test_openai_compat.py -k "compact_context or post_response_effects or post_response_compaction or openai_stream_response"'` passed: 30 passed, 183 deselected.
- `nix-shell --run 'uv run pytest -n 0 --no-cov tests/test_compact_context.py tests/test_compaction.py tests/test_agno_history.py tests/test_openai_compat.py tests/test_tools_metadata.py'` passed: 335 passed.
- `nix-shell --run 'uv run ruff check src/mindroom/history/runtime.py src/mindroom/custom_tools/compact_context.py src/mindroom/tools/compact_context.py tests/test_agno_history.py tests/test_compact_context.py tests/test_compaction.py'` passed.
- R1: `nix-shell --run 'uv run pytest -n 0 --no-cov tests/test_agno_history.py -k "uses_compaction_model_window_when_active_model_has_none"'` passed: 1 passed, 105 deselected.
- R1: `nix-shell --run 'uv run pytest -n 0 --no-cov tests/test_agno_history.py -k "post_response_compaction_check or post_response_check"'` passed: 11 passed, 95 deselected.
- R1: `nix-shell --run 'uv run pytest -n 0 --no-cov tests/test_compact_context.py -k "compaction_model_window_when_active_model_has_none"'` passed: 1 passed, 15 deselected.
- R1: `nix-shell --run 'uv run ruff check src/mindroom/history/runtime.py tests/test_agno_history.py'` passed.

## Phase 4 Acceptance Evidence

Evidence directory: `/tmp/ISSUE-202-evidence/`.

Files:

- `README.md`: evidence summary and exact commands.
- `test-output.txt`: focused pytest output for the same-turn manual post-response path, R1 active-model-None edge case, and failed/non-finalized fallback.
- `smoke_harness.py` / `smoke-output.txt`: in-process acceptance smoke using temporary SQLite storage, the real `compact_context()` tool marker, `apply_post_response_effects()`, and `run_post_response_compaction_check()`.
- `diff-stat.txt`: `git diff --stat origin/main...HEAD`.
- `git-sha.txt`: reviewed branch, HEAD, merge-base, recent commits, and clean source status.

Focused acceptance command:

```bash
nix-shell --run 'uv run pytest -n 0 --no-cov -vv tests/test_compact_context.py::test_compact_context_sets_force_flag_for_agent_scope tests/test_compaction.py::test_post_response_effects_start_compaction_check_after_response_link_persistence tests/test_agno_history.py::test_prepare_history_for_run_records_post_response_check_for_manual_capable_auto_disabled_scope tests/test_agno_history.py::test_run_post_response_compaction_check_runs_forced_manual_with_auto_disabled_scope tests/test_agno_history.py::test_run_post_response_compaction_check_uses_compaction_model_window_when_active_model_has_none tests/test_compaction.py::test_post_response_effects_skip_compaction_without_finalized_assistant_event tests/test_agno_history.py::test_prepare_history_for_run_required_compaction_starts_lifecycle_before_summary_request'
```

Result: 7 passed, 1 warning in 2.96s.

Smoke command:

```bash
nix-shell --run 'uv run python /tmp/ISSUE-202-evidence/smoke_harness.py'
```

Result: passed all three acceptance scenarios:

- Same-turn/post-response path: the harness invoked `compact_context()`, finalized a visible assistant event `$assistant-final`, persisted response linkage, ran manual post-response compaction immediately, wrote the summary, and cleared the force marker.
- R1 edge case: active runtime model had `context_window=None`, explicit summary model had `context_window=32000`, and forced manual post-response compaction completed with `history_budget_tokens=None`.
- Failed/cancelled fallback: cancelled/no-event post-response skipped compaction, left the force marker intact, and the next-turn foreground required compaction consumed it.

No production services were started or restarted. The smoke harness is the lightweight live substitute for this backend lifecycle path because it executes the real post-response gate and compaction runner against isolated temporary storage with fake summary-model calls, avoiding production Matrix/runtime side effects while still proving the actual ordering and state transitions.
