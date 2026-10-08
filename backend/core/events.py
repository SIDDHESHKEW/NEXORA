"""In-process event bus for decoupled event emission and listener dispatch."""

import asyncio
import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger("sgsu.events")


class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable[..., Any]]] = {}

    def subscribe(self, event_name: str, callback: Callable[..., Any]) -> None:
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    async def emit(self, event_name: str, **kwargs: Any) -> None:
        """Emit an event asynchronously to all subscribed handlers."""
        listeners = self._listeners.get(event_name, [])
        for handler in listeners:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(**kwargs)
                else:
                    handler(**kwargs)
            except Exception as e:
                logger.error(f"Error executing listener for {event_name}: {e}", exc_info=True)


event_bus = EventBus()
