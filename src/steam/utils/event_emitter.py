import asyncio
import inspect
import logging
from typing import Callable, Any, Optional, Union
from collections import defaultdict


class EventEmitter:
    """
    A simple async event emitter.
    """

    def __init__(self):
        self._listeners: dict[Any,
                              list[Callable[..., Any]]] = defaultdict(list)
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
                    self._log.error(f"Error in event handler for {event}: {e}")

    async def wait_for(self, event: Any, timeout: Union[float, int, None] = None, check: Optional[Callable[..., bool]] = None) -> Any:
        """
        Waits for an event to be emitted.

        Args:
            event: The event to wait for.
            timeout: The maximum time to wait in seconds.
            check: A predicate function that checks the event data. 
                   Should return True if the event is the one we want.

        Returns:
            The arguments passed to emit() for the event.
        """
        future: asyncio.Future[Any] = asyncio.Future()

        def listener(*args: Any, **kwargs: Any):
            if check is not None:
                try:
                    if not check(*args, **kwargs):
                        return
                except Exception as e:
                    self._log.error(
                        f"Error in check function for {event}: {e}")
                    return

            if not future.done():
                if len(args) == 1:
                    future.set_result(args[0])
                else:
                    future.set_result(args)

                self.remove_listener(event, listener)

        self.on(event, listener)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self.remove_listener(event, listener)
            raise
