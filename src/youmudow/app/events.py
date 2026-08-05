"""Event system for YouMuDow.

Simple pub/sub event bus for communication between layers.
Used to deliver real-time log output from services to the UI.
"""

import datetime
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Application event types."""

    LOG_OUTPUT = auto()
    LOG_CLEAR = auto()


@dataclass
class Event:
    """Base event class."""

    type: EventType


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
    _initialized: bool

    def __new__(cls) -> "EventBus":  # noqa: PYI034 - typing.Self requires Python 3.11
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
        self._subscribe_lock = threading.Lock()
        self._initialized = True

    def subscribe(self, event_type: EventType, handler: Handler) -> Unsubscribe:
        with self._subscribe_lock:
            self._handlers.setdefault(event_type, []).append(handler)

        def unsubscribe() -> None:
            self.unsubscribe(event_type, handler)

        return unsubscribe

    def unsubscribe(self, event_type: EventType, handler: Handler) -> None:
        with self._subscribe_lock:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
        with self._subscribe_lock:
            handlers = list(self._handlers.get(event.type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Handler error in event bus")

    def clear(self) -> None:
        with self._subscribe_lock:
            self._handlers.clear()

    @classmethod
    def get_instance(cls) -> "EventBus":
        return cls()

    @classmethod
    def reset(cls) -> None:
        """Reset singleton for testing. Do not use in production code."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.clear()
                cls._instance = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return EventBus.get_instance()


def emit(event: Event) -> None:
    """Publish an event to the global bus."""
    get_event_bus().publish(event)


def emit_log(message: str, level: str = "info") -> None:
    """Emit a log message event for terminal display."""
    timestamp = datetime.datetime.now().astimezone().strftime("%H:%M:%S")
    emit(
        LogEvent(
            type=EventType.LOG_OUTPUT,
            message=message,
            level=level,
            timestamp=timestamp,
        )
    )
