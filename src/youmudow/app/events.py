"""Event system for YouMuDow.

Simple pub/sub event system for communication between layers.
"""

import threading
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, TypeVar

from youmudow.domain.models import Video


T = TypeVar("T")


class EventType(Enum):
    """Application event types."""

    SEARCH_STARTED = auto()
    SEARCH_COMPLETED = auto()
    SEARCH_ERROR = auto()

    DOWNLOAD_QUEUED = auto()
    DOWNLOAD_STARTED = auto()
    DOWNLOAD_PROGRESS = auto()
    DOWNLOAD_COMPLETED = auto()
    DOWNLOAD_ERROR = auto()
    DOWNLOAD_CANCELLED = auto()

    LOG_OUTPUT = auto()
    LOG_CLEAR = auto()

    STATE_CHANGED = auto()
    SELECTION_CHANGED = auto()


@dataclass
class Event:
    """Base event class."""

    type: EventType


@dataclass
class SearchEvent(Event):
    """Search-related events."""

    query: str = ""
    results: list[Video] | None = None
    error: str | None = None


@dataclass
class DownloadEvent(Event):
    """Download-related events."""

    video: Video | None = None
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    error: str | None = None


@dataclass
class StateChangeEvent(Event):
    """State change events."""

    state_name: str = ""
    old_state: str = ""
    new_state: str = ""


@dataclass
class SelectionEvent(Event):
    """Selection change events."""

    video: Video | None = None
    index: int = -1


@dataclass
class LogEvent(Event):
    """Log output event for real-time terminal display."""

    message: str = ""
    level: str = "info"
    timestamp: str = ""


Handler = Callable[[Event], None]
Unsubscribe = Callable[[], None]


class EventBus:
    """Simple pub/sub event bus."""

    _instance: "EventBus | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._handlers: dict[EventType, list[Handler]] = {}
        self._global_handlers: list[Handler] = []
        self._subscribe_lock = threading.Lock()
        self._initialized = True

    def subscribe(self, event_type: EventType, handler: Handler) -> Unsubscribe:
        with self._subscribe_lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

        def unsubscribe() -> None:
            self.unsubscribe(event_type, handler)

        return unsubscribe

    def subscribe_any(self, handler: Handler) -> Unsubscribe:
        with self._subscribe_lock:
            self._global_handlers.append(handler)

        def unsubscribe() -> None:
            self.unsubscribe_any(handler)

        return unsubscribe

    def unsubscribe(self, event_type: EventType, handler: Handler) -> None:
        with self._subscribe_lock:
            if event_type in self._handlers:
                try:
                    self._handlers[event_type].remove(handler)
                except ValueError:
                    pass

    def unsubscribe_any(self, handler: Handler) -> None:
        with self._subscribe_lock:
            try:
                self._global_handlers.remove(handler)
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
        with self._subscribe_lock:
            handlers = list(self._handlers.get(event.type, []))
            global_handlers = list(self._global_handlers)

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                import sys
                print(f"[EventBus] Handler error: {e}", file=sys.stderr)

        for handler in global_handlers:
            try:
                handler(event)
            except Exception as e:
                import sys
                print(f"[EventBus] Handler error: {e}", file=sys.stderr)

    def clear(self) -> None:
        with self._subscribe_lock:
            self._handlers.clear()
            self._global_handlers.clear()

    @classmethod
    def get_instance(cls) -> "EventBus":
        return cls()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return EventBus.get_instance()


def emit(event: Event) -> None:
    """Publish an event to the global bus."""
    get_event_bus().publish(event)


def on(
    event_type: EventType,
) -> Callable[[Handler], Handler]:
    """Decorator to subscribe to an event type."""
    def decorator(handler: Handler) -> Handler:
        get_event_bus().subscribe(event_type, handler)
        return handler
    return decorator


def emit_search_started(query: str) -> None:
    emit(SearchEvent(type=EventType.SEARCH_STARTED, query=query))


def emit_search_completed(query: str, results: list[Video]) -> None:
    emit(SearchEvent(type=EventType.SEARCH_COMPLETED, query=query, results=results))


def emit_search_error(query: str, error: str) -> None:
    emit(SearchEvent(type=EventType.SEARCH_ERROR, query=query, error=error))


def emit_download_queued(video: Video) -> None:
    emit(DownloadEvent(type=EventType.DOWNLOAD_QUEUED, video=video))


def emit_download_started(video: Video) -> None:
    emit(DownloadEvent(type=EventType.DOWNLOAD_STARTED, video=video))


def emit_download_progress(
    video: Video,
    progress: float,
    speed: str = "",
    eta: str = "",
) -> None:
    emit(DownloadEvent(
        type=EventType.DOWNLOAD_PROGRESS,
        video=video,
        progress=progress,
        speed=speed,
        eta=eta,
    ))


def emit_download_completed(video: Video) -> None:
    emit(DownloadEvent(type=EventType.DOWNLOAD_COMPLETED, video=video))


def emit_download_error(video: Video, error: str) -> None:
    emit(DownloadEvent(type=EventType.DOWNLOAD_ERROR, video=video, error=error))


def emit_download_cancelled(video: Video) -> None:
    emit(DownloadEvent(type=EventType.DOWNLOAD_CANCELLED, video=video))


def emit_state_changed(old_state: str, new_state: str) -> None:
    emit(StateChangeEvent(
        type=EventType.STATE_CHANGED,
        state_name=new_state,
        old_state=old_state,
        new_state=new_state,
    ))


def emit_selection_changed(video: Video | None, index: int = -1) -> None:
    emit(SelectionEvent(type=EventType.SELECTION_CHANGED, video=video, index=index))


def emit_log(message: str, level: str = "info") -> None:
    """Emit a log message event for terminal display."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    emit(LogEvent(
        type=EventType.LOG_OUTPUT,
        message=message,
        level=level,
        timestamp=timestamp,
    ))


def clear_logs() -> None:
    """Clear the log display."""
    emit(LogEvent(type=EventType.LOG_CLEAR))
