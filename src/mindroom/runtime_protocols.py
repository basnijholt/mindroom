"""Narrow runtime Protocols for extracted bot collaborators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import nio

    from mindroom.config.main import Config
    from mindroom.matrix.cache import ConversationEventCache, EventCacheWriteCoordinator
    from mindroom.orchestrator import MultiAgentOrchestrator


class SupportsConfig(Protocol):
    """Expose the runtime config snapshot."""

    @property
    def config(self) -> Config: ...  # noqa: D102


class SupportsEventCache(Protocol):
    """Expose the conversation event cache."""

    @property
    def event_cache(self) -> ConversationEventCache: ...  # noqa: D102


class SupportsEventCacheWriteCoordinator(Protocol):
    """Expose coordinated event-cache write access."""

    @property
    def event_cache_write_coordinator(self) -> EventCacheWriteCoordinator: ...  # noqa: D102


class SupportsClientConfig(Protocol):
    """Expose the Matrix client plus runtime config."""

    @property
    def client(self) -> nio.AsyncClient | None: ...  # noqa: D102

    @property
    def config(self) -> Config: ...  # noqa: D102


class SupportsConfigOrchestrator(SupportsConfig, Protocol):
    """Expose the config plus optional orchestrator handle."""

    @property
    def orchestrator(self) -> MultiAgentOrchestrator | None: ...  # noqa: D102


class SupportsClientConfigEventCache(SupportsClientConfig, Protocol):
    """Expose client/config access plus the event cache."""

    @property
    def event_cache(self) -> ConversationEventCache: ...  # noqa: D102


class SupportsClientConfigOrchestrator(SupportsClientConfig, Protocol):
    """Expose client/config access plus the orchestrator."""

    @property
    def orchestrator(self) -> MultiAgentOrchestrator | None: ...  # noqa: D102


class SupportsThreadWriteCacheRuntime(Protocol):
    """Expose the cache state needed for thread write bookkeeping."""

    @property
    def event_cache(self) -> ConversationEventCache: ...  # noqa: D102

    @property
    def event_cache_write_coordinator(self) -> EventCacheWriteCoordinator: ...  # noqa: D102

    @property
    def runtime_started_at(self) -> float: ...  # noqa: D102


class SupportsConversationCacheRuntime(SupportsThreadWriteCacheRuntime, Protocol):
    """Expose thread write cache state plus the Matrix client."""

    @property
    def client(self) -> nio.AsyncClient | None: ...  # noqa: D102


class SupportsResponseRunnerRuntime(SupportsClientConfigOrchestrator, Protocol):
    """Expose the runtime surface needed by response execution."""

    @property
    def enable_streaming(self) -> bool: ...  # noqa: D102


class SupportsTurnControllerRuntime(SupportsClientConfigOrchestrator, Protocol):
    """Expose the runtime surface needed by turn control."""

    @property
    def event_cache(self) -> ConversationEventCache: ...  # noqa: D102


if TYPE_CHECKING:
    from mindroom.bot_runtime_view import BotRuntimeView

    def _check_narrow_protocols_are_subsets_of_bot_runtime_view(
        view: BotRuntimeView,
    ) -> None:
        """Type-only proof that BotRuntimeView satisfies every narrow protocol.

        This function is never called at runtime. The assignments below
        will fail static type-check if any narrow protocol drifts out of
        the BotRuntimeView surface.
        """
        _a: SupportsConfig = view
        _b: SupportsEventCache = view
        _c: SupportsEventCacheWriteCoordinator = view
        _d: SupportsClientConfig = view
        _e: SupportsConfigOrchestrator = view
        _f: SupportsClientConfigEventCache = view
        _g: SupportsClientConfigOrchestrator = view
        _h: SupportsThreadWriteCacheRuntime = view
        _i: SupportsConversationCacheRuntime = view
        _j: SupportsResponseRunnerRuntime = view
        _k: SupportsTurnControllerRuntime = view
