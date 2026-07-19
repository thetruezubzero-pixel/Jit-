"""Observer-style event bus for cross-module communication."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class Event:
    topic: str
    payload: dict[str, Any]


Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)

    def subscribe(self, topic: str, callback: Subscriber) -> None:
        self._subscribers[topic].append(callback)

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        event = Event(topic=topic, payload=payload)
        for callback in [*self._subscribers.get(topic, []), *self._subscribers.get("*", [])]:
            callback(event)
