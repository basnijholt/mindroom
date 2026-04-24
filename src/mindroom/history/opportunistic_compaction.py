"""In-process queue for opportunistic history compaction."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from mindroom.history.runtime import (
    resolve_scope_storage_identity,
    run_post_response_compaction_check,
)
from mindroom.history.types import HistoryScope, PostResponseCompactionCheck
from mindroom.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from mindroom.config.main import Config
    from mindroom.constants import RuntimePaths
    from mindroom.history.types import CompactionLifecycle
    from mindroom.tool_system.worker_routing import ToolExecutionIdentity

logger = get_logger(__name__)


@dataclass(frozen=True)
class OpportunisticCompactionKey:
    """Dedupe identity for one persisted opportunistic compaction target."""

    agent_name: str
    scope_kind: str
    scope_id: str
    session_id: str
    storage_identity: str


@dataclass(frozen=True)
class _OpportunisticCompactionEntry:
    key: OpportunisticCompactionKey
    check: PostResponseCompactionCheck
    runtime_paths: RuntimePaths
    config: Config
    execution_identity: ToolExecutionIdentity | None
    compaction_lifecycle: CompactionLifecycle | None
    enqueued_at: float


@dataclass
class _RunningEntry:
    entry: _OpportunisticCompactionEntry
    dirty_entry: _OpportunisticCompactionEntry | None = None
    awaiting_active_enqueue: bool = False


@dataclass
class _QueueState:
    queue: asyncio.Queue[OpportunisticCompactionKey]
    pending: dict[OpportunisticCompactionKey, _OpportunisticCompactionEntry]
    queued_keys: set[OpportunisticCompactionKey]
    running: dict[OpportunisticCompactionKey, _RunningEntry]
    worker_task: asyncio.Task[None] | None = None


_QUEUE_STATES: WeakKeyDictionary[asyncio.AbstractEventLoop, _QueueState] = WeakKeyDictionary()


def _state_for_loop(loop: asyncio.AbstractEventLoop) -> _QueueState:
    state = _QUEUE_STATES.get(loop)
    if state is None:
        state = _QueueState(
            queue=asyncio.Queue(),
            pending={},
            queued_keys=set(),
            running={},
        )
        _QUEUE_STATES[loop] = state
    return state


def _key_for_check(check: PostResponseCompactionCheck) -> OpportunisticCompactionKey:
    return OpportunisticCompactionKey(
        agent_name=check.agent_name,
        scope_kind=check.scope_kind,
        scope_id=check.scope_id,
        session_id=check.session_id,
        storage_identity=check.storage_identity,
    )


def enqueue_opportunistic_compactions(
    checks: Sequence[PostResponseCompactionCheck],
    *,
    runtime_paths: RuntimePaths,
    config: Config,
    execution_identity: ToolExecutionIdentity | None,
    compaction_lifecycle: CompactionLifecycle | None = None,
) -> None:
    """Queue opportunistic compaction checks and return immediately."""
    if not checks:
        return
    loop = asyncio.get_running_loop()
    state = _state_for_loop(loop)
    _ensure_worker(state)

    for check in checks:
        key = _key_for_check(check)
        entry = _OpportunisticCompactionEntry(
            key=key,
            check=check,
            runtime_paths=runtime_paths,
            config=config,
            execution_identity=execution_identity,
            compaction_lifecycle=compaction_lifecycle,
            enqueued_at=time.monotonic(),
        )
        running = state.running.get(key)
        if running is not None:
            running.dirty_entry = entry
            running.awaiting_active_enqueue = False
            logger.info(
                "Marked running opportunistic compaction dirty",
                agent=key.agent_name,
                session_id=key.session_id,
                scope=f"{key.scope_kind}:{key.scope_id}",
                storage_identity=key.storage_identity,
            )
            continue

        state.pending[key] = entry
        if key not in state.queued_keys:
            state.queued_keys.add(key)
            state.queue.put_nowait(key)
        logger.info(
            "Queued opportunistic compaction",
            agent=key.agent_name,
            session_id=key.session_id,
            scope=f"{key.scope_kind}:{key.scope_id}",
            storage_identity=key.storage_identity,
        )


def reprioritize_opportunistic_compactions(
    *,
    agent_name: str,
    session_id: str,
    runtime_paths: RuntimePaths,
    config: Config,
    execution_identity: ToolExecutionIdentity | None,
    scope: HistoryScope | None = None,
) -> None:
    """Hold stale pending work for the active session and mark running work dirty."""
    loop = asyncio.get_running_loop()
    active_scope = scope or HistoryScope(kind="agent", scope_id=agent_name)
    state = _QUEUE_STATES.get(loop)
    if state is None:
        return
    matching_keys = [
        key
        for key in (*state.pending.keys(), *state.running.keys())
        if key.scope_kind == active_scope.kind
        and key.scope_id == active_scope.scope_id
        and key.session_id == session_id
    ]
    if not matching_keys:
        return
    storage_identity = resolve_scope_storage_identity(
        agent_name=agent_name,
        scope=active_scope,
        runtime_paths=runtime_paths,
        config=config,
        execution_identity=execution_identity,
    )
    active_keys = [key for key in matching_keys if key.storage_identity == storage_identity]
    for active_key in active_keys:
        if active_key not in state.pending:
            continue
        state.pending.pop(active_key, None)
        state.queued_keys.discard(active_key)
        logger.info(
            "Held pending opportunistic compaction for active session",
            agent=active_key.agent_name,
            session_id=session_id,
            scope=active_scope.key,
            storage_identity=storage_identity,
        )
    for active_key in active_keys:
        running = state.running.get(active_key)
        if running is not None:
            running.dirty_entry = None
            running.awaiting_active_enqueue = True
            logger.info(
                "Held running opportunistic compaction rerun for active session",
                agent=active_key.agent_name,
                session_id=session_id,
                scope=active_scope.key,
                storage_identity=storage_identity,
            )


async def drain_opportunistic_compactions(*, wait_timeout: float = 5.0) -> None:
    """Wait for queued opportunistic compaction work in the current event loop."""
    loop = asyncio.get_running_loop()
    state = _QUEUE_STATES.get(loop)
    if state is None:
        return
    await asyncio.wait_for(state.queue.join(), timeout=wait_timeout)


async def reset_opportunistic_compaction_queue_for_tests() -> None:
    """Clear current-loop queue state and stop its worker."""
    loop = asyncio.get_running_loop()
    state = _QUEUE_STATES.pop(loop, None)
    if state is None:
        return
    if state.worker_task is not None:
        state.worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await state.worker_task


def queued_opportunistic_compaction_count() -> int:
    """Return pending/running work count for tests and diagnostics."""
    loop = asyncio.get_running_loop()
    state = _QUEUE_STATES.get(loop)
    if state is None:
        return 0
    return len(state.pending) + len(state.running)


def _ensure_worker(state: _QueueState) -> None:
    if state.worker_task is not None and not state.worker_task.done():
        return
    state.worker_task = asyncio.create_task(_worker(state), name="opportunistic_compaction_worker")


async def _worker(state: _QueueState) -> None:
    while True:
        key = await state.queue.get()
        try:
            state.queued_keys.discard(key)
            entry = state.pending.pop(key, None)
            if entry is None:
                continue
            while entry is not None:
                running = _RunningEntry(entry=entry)
                state.running[key] = running
                try:
                    await run_post_response_compaction_check(
                        check=entry.check,
                        runtime_paths=entry.runtime_paths,
                        config=entry.config,
                        execution_identity=entry.execution_identity,
                        compaction_lifecycle=entry.compaction_lifecycle,
                    )
                except Exception:
                    logger.exception(
                        "Opportunistic compaction failed",
                        agent=key.agent_name,
                        session_id=key.session_id,
                        scope=f"{key.scope_kind}:{key.scope_id}",
                        storage_identity=key.storage_identity,
                    )
                finally:
                    state.running.pop(key, None)
                entry = running.dirty_entry
                if running.awaiting_active_enqueue and entry is None:
                    logger.info(
                        "Skipped stale active-session opportunistic compaction rerun",
                        agent=key.agent_name,
                        session_id=key.session_id,
                        scope=f"{key.scope_kind}:{key.scope_id}",
                        storage_identity=key.storage_identity,
                    )
        finally:
            state.queue.task_done()
