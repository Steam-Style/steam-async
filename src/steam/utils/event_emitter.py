import asyncio
import dataclasses
import inspect
import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any


@dataclasses.dataclass
class EventStream:
    queue: "asyncio.Queue[Any]"
    _client: Any
    _event: Any
    _listener: Callable[..., Any]

    def close(self) -> None:
        self._client.remove_listener(self._event, self._listener)


class EventEmitter:
    """
    A simple async event emitter.
    """

    def __init__(self):
        self._listeners: dict[Any, list[Callable[..., Any]]] = defaultdict(list)
        self._log = logging.getLogger(__name__)

    def on(self, event: Any, callback: Callable[..., Any]):
        """
        Registers a callback for an event.

        Args:
            event: The event to listen for.
            callback: The function to call when the event is emitted.
        """
        self._listeners[event].append(callback)

    def remove_listener(self, event: Any, callback: Callable[..., Any]):
        """
        Removes a callback for an event.

        Args:
            event: The event the callback is registered for.
            callback: The callback to remove.
        """
        if event in self._listeners:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                pass

    def emit(self, event: Any, *args: Any, **kwargs: Any):
        """
        Emits an event, calling all registered callbacks.

        Args:
            event: The event to emit.
            *args: Positional arguments to pass to the callbacks.
            **kwargs: Keyword arguments to pass to the callbacks.
        """
        if event in self._listeners:
            for callback in self._listeners[event]:
                try:
                    if inspect.iscoroutinefunction(callback):
                        asyncio.create_task(callback(*args, **kwargs))
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    self._log.error("Error in event handler for %s: %s", event, e)

    def create_listener(
        self,
        event: Any,
        check: Callable[..., bool] | None = None,
    ) -> asyncio.Future[Any]:
        """
        Registers a one-time listener for an event that returns a future.

        Args:
            event: The event to wait for.
            check: A predicate function that checks the event data. Should return True if the event is the one we want.

        Returns:
            A future that will be set when the event is emitted and passes the check.
        """
        future: asyncio.Future[Any] = asyncio.Future()

        def listener(*args: Any, **kwargs: Any):
            if check is not None:
                try:
                    if not check(*args, **kwargs):
                        return
                except Exception as e:
                    self._log.error("Error in check function for %s: %s", event, e)
                    return

            if not future.done():
                future.set_result(args[0] if len(args) == 1 else args)
                self.remove_listener(event, listener)

        self.on(event, listener)
        return future

    def create_stream_listener(
        self,
        event: Any,
        check: Callable[..., bool] | None = None,
    ) -> EventStream:
        """
        Registers a persistent listener that pushes every matching event onto a queue.

        Args:
            event: The event to listen for.
            check: A predicate function that checks the event data. Should return True if the event is the one we want.

        Returns:
            An EventStream object containing the queue and methods to manage the listener.
        """
        queue: asyncio.Queue[Any] = asyncio.Queue()

        def listener(*args: Any, **kwargs: Any):
            if check is not None:
                try:
                    if not check(*args, **kwargs):
                        return
                except Exception as e:
                    self._log.error("Error in check function for %s: %s", event, e)
                    return
            queue.put_nowait(args[0] if len(args) == 1 else args)

        self.on(event, listener)
        return EventStream(queue=queue, _client=self, _event=event, _listener=listener)
