"""Tests for EventBus."""

from youmudow.app.events import (
    EventBus,
    EventType,
    LogEvent,
    get_event_bus,
)


class TestEventBus:
    def test_singleton(self):
        b1 = get_event_bus()
        b2 = get_event_bus()
        assert b1 is b2

    def test_subscribe_and_publish(self):
        bus = EventBus()
        results = []
        bus.subscribe(EventType.LOG_OUTPUT, lambda e: results.append(e))
        event = LogEvent(type=EventType.LOG_OUTPUT, message="test")
        bus.publish(event)
        assert len(results) == 1
        assert results[0].message == "test"

    def test_unsubscribe(self):
        bus = EventBus()
        results = []

        def handler(e: object) -> None:
            results.append(1)

        unsub = bus.subscribe(EventType.LOG_OUTPUT, handler)
        bus.publish(LogEvent(type=EventType.LOG_OUTPUT))
        assert len(results) == 1
        unsub()
        bus.publish(LogEvent(type=EventType.LOG_OUTPUT))
        assert len(results) == 1

    def test_no_handler_error(self):
        bus = EventBus()
        bus.publish(LogEvent(type=EventType.LOG_OUTPUT))

    def test_handler_exception_does_not_crash(self):
        bus = EventBus()

        def bad(e):
            raise ValueError("oops")

        bus.subscribe(EventType.LOG_OUTPUT, bad)
        bus.publish(LogEvent(type=EventType.LOG_OUTPUT))

    def test_clear(self):
        bus = EventBus()
        results = []
        bus.subscribe(EventType.LOG_OUTPUT, lambda e: results.append(1))
        bus.clear()
        bus.publish(LogEvent(type=EventType.LOG_OUTPUT))
        assert len(results) == 0

    def test_log_event(self):
        e = LogEvent(type=EventType.LOG_OUTPUT, message="hello", level="info")
        assert e.message == "hello"
        assert e.level == "info"

    def test_emit_log_uses_global_bus(self):
        bus = get_event_bus()
        results = []
        bus.subscribe(EventType.LOG_OUTPUT, lambda e: results.append(e.message))
        from youmudow.app.events import emit_log

        emit_log("hello")
        assert "hello" in results
