# History Compaction Lifecycle Plan

Last updated: 2026-04-24
Owner: MindRoom backend
Status: Proposed

## Problem

Foreground automatic history compaction can currently make a response appear stuck after the visible `Thinking...` placeholder is posted.
The 2026-04-24 production trace for event `$4LFQhtkwJc_Z467SG-fNRprVhelgsFhUnsb6eSAl36s` spent about 300 seconds in `system_prompt_assembly.history_prepare.compaction.summary_model_request`.
That same trace spent about 42 seconds in the actual provider response request after compaction failed.
The immediate latency issue was therefore foreground compaction, but compaction is not the only possible source of slow replies.
The current Matrix compaction notice is also posted after final response delivery, which makes the room ordering misleading.

## Goals

- Keep response latency predictable when compaction is only maintenance.
- Preserve context quality when compaction is required for the next answer.
- Make compaction visible in the room before it blocks a response.
- Update the same compaction message with final stats instead of posting a late notice after the reply.
- Make timing logs identify whether time was spent in cache reads, compaction, prompt assembly, provider latency, streaming, delivery, or post-response effects.

## Non-Goals

- Do not hide required compaction by always moving it to the background.
- Do not rely on post-response notices for compaction that affected the current reply.
- Do not make Matrix notice delivery part of the critical compaction data path.
- Do not remove safe replay trimming as a fallback when compaction fails.

## Policy

### Opportunistic Auto-Compaction

Use this path when history is above the configured threshold but the current turn can still fit with acceptable replay quality.
The agent should reply without waiting for compaction.
After the reply reaches a terminal state, mark the session for background compaction.
The background job should deduplicate by `(agent, scope, session_id)`.
The background job should be reprioritized when the same session becomes active again.
This is the common path for maintenance and should not add user-visible latency.

### Required Foreground Compaction

Use this path when the next answer would otherwise require dropping material history that should be preserved as a summary.
Before starting compaction, send a visible thread notice such as `Compacting history...`.
Block the current model call until compaction finishes, fails, or reaches a configured timeout.
On success, edit the same notice with before and after token counts, compacted run count, duration, summary model, and history budget.
On failure, edit the same notice with the failure mode and state that the reply will continue with trimmed history.
Only then proceed to model generation.

### Manual Or Forced Compaction

Manual compaction should always use the foreground path.
The user asked for compaction, so the visible ordering should show compaction before the reply that depends on it.
The final notice should be edited in place with complete stats.

## Lifecycle

1. A request reaches the response runner and posts `Thinking...` when needed.
2. History preparation classifies the compaction need as `none`, `opportunistic`, or `required`.
3. For `none`, history preparation proceeds directly to replay planning.
4. For `opportunistic`, history preparation records a post-response compaction request and proceeds directly to replay planning.
5. For `required`, history preparation sends a compaction progress notice in the target thread before calling the summary model.
6. Required compaction edits the progress notice on success, failure, or timeout.
7. The model request starts only after required compaction has resolved.
8. Post-response effects enqueue any recorded opportunistic compaction work.
9. Background compaction may send a low-priority maintenance notice only if configured.

## Notice Design

The initial notice should be a Matrix `m.notice` in the resolved response thread.
The initial notice should not mention users.
The initial notice should use stable structured content metadata so clients can render it specially later.
The completion update should edit the same event rather than post a new event.
The completed notice should include `mode`, `session_id`, `scope`, `summary_model`, `before_tokens`, `after_tokens`, `history_budget_tokens`, `runs_before`, `runs_after`, `compacted_run_count`, `duration_ms`, and `status`.
The failed notice should include the same identity fields plus `status`, `duration_ms`, and a short failure reason.
The old post-response compaction notice path should remain only as a fallback for compaction outcomes without an active lifecycle notice.

## Implementation Plan

### Phase 1: Classification

Add an explicit compaction decision type with values `none`, `opportunistic`, and `required`.
Base `opportunistic` on configured threshold pressure when a safe replay plan still fits.
Base `required` on cases where replay trimming would drop compactable old runs that should instead be represented by the durable summary.
Keep manual `force_compact_before_next_run` as `required`.
Log the decision with current history tokens, replay budget, estimated fitted replay tokens, and reason.

### Phase 2: Post-Reply Opportunistic Queue

Remove pre-reply auto-compaction scheduling from ordinary automatic compaction.
Add a post-response effect that marks the completed session dirty for background compaction.
Run the background compaction worker after final response delivery and memory dirty marking.
Deduplicate active jobs per session.
Persist each successful compaction chunk so partial progress survives later provider failures.

### Phase 3: Foreground Progress Notice

Add a small compaction lifecycle object that can send and edit one Matrix notice.
Thread that lifecycle object through agent and team history preparation.
Send the initial notice before required compaction starts.
Edit the notice after compaction completes, times out, or fails.
Avoid dispatching a second post-response compaction notice when a lifecycle notice was used.

### Phase 4: Safer Summary Calls

Reduce the default per-call summary input budget below the provider window with a conservative reserve.
Chunk selected runs into smaller summary calls.
If a provider rejects or times out, retry with a smaller chunk before giving up.
Use a shorter per-chunk timeout so one failed summary call cannot block for five minutes.
Log per-chunk token estimates and durations.

### Phase 5: Timing And Metadata

Split `diag_llm_prepare_ms` into narrower fields for memory search, agent construction, history classification, required compaction, replay planning, and final prompt assembly.
Record whether the current reply used `none`, `opportunistic`, `required_success`, `required_failed`, or `required_timeout`.
Expose cumulative prepared context tokens in Matrix run metadata.
Keep provider token usage separate from prepared context estimates.

## Tests

- Unit test that opportunistic compaction is queued only after response finalization.
- Unit test that required compaction sends the progress notice before the model request starts.
- Unit test that required compaction edits the same notice on success.
- Unit test that required compaction edits the same notice on timeout and then falls back to trimmed replay.
- Unit test that post-response compaction notices are skipped when a lifecycle notice exists.
- Integration-style test for Matrix thread targeting so first-turn threaded replies keep compaction notices in the resolved thread.
- Timing test that `diag_llm_prepare_ms` no longer hides a 300 second compaction subspan.

## Migration From Current Patch

The current commit `fix(history): keep auto compaction off reply path` should be treated as an interim latency guard.
It should be replaced or amended so automatic compaction is not simply always moved to the background.
The final behavior should background only opportunistic compaction and keep required compaction foreground with an ordered visible lifecycle notice.
