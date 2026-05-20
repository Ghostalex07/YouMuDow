"""Tests for EventBus."""
from youmudow.app.events import (
    EventBus, EventType, Event, SearchEvent, DownloadEvent,
    LogEvent, get_event_bus,
)
from youmudow.domain.models import Video


class TestEventBus:
    def test_singleton(self):
        b1 = get_event_bus()
        b2 = get_event_bus()
        assert b1 is b2

    def test_subscribe_and_publish(self):
        bus = EventBus()
        results = []
        bus.subscribe(EventType.SEARCH_STARTED, lambda e: results.append(e))
        event = SearchEvent(type=EventType.SEARCH_STARTED, query="test")
        bus.publish(event)
        assert len(results) == 1
        assert results[0].query == "test"

    def test_unsubscribe(self):
        bus = EventBus()
        results = []
        def handler(e: object) -> None:
            results.append(1)
        unsub = bus.subscribe(EventType.SEARCH_STARTED, handler)
        bus.publish(SearchEvent(type=EventType.SEARCH_STARTED))
        assert len(results) == 1
        unsub()
        bus.publish(SearchEvent(type=EventType.SEARCH_STARTED))
        assert len(results) == 1

    def test_subscribe_any(self):
        bus = EventBus()
        results = []
        bus.subscribe_any(lambda e: results.append(e.type))
        bus.publish(Event(type=EventType.SEARCH_STARTED))
        bus.publish(Event(type=EventType.DOWNLOAD_STARTED))
        assert len(results) == 2

    def test_no_handler_error(self):
        bus = EventBus()
        bus.publish(Event(type=EventType.SEARCH_STARTED))

    def test_handler_exception_does_not_crash(self):
        bus = EventBus()
        def bad(e):
            raise ValueError("oops")
        bus.subscribe(EventType.SEARCH_STARTED, bad)
        bus.publish(SearchEvent(type=EventType.SEARCH_STARTED))

    def test_clear(self):
        bus = EventBus()
        results = []
        bus.subscribe(EventType.SEARCH_STARTED, lambda e: results.append(1))
        bus.clear()
        bus.publish(SearchEvent(type=EventType.SEARCH_STARTED))
        assert len(results) == 0

    def test_log_event(self):
        e = LogEvent(type=EventType.LOG_OUTPUT, message="hello", level="info")
        assert e.message == "hello"
        assert e.level == "info"

    def test_download_event_with_video(self):
        v = Video(title="T", url="u")
        e = DownloadEvent(type=EventType.DOWNLOAD_STARTED, video=v)
        assert e.video.title == "T"
