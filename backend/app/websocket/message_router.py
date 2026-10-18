"""Dispatch validated message models; role routers choose the permitted subset."""

from collections.abc import Awaitable, Callable

from app.models.messages import BaseMsg

Handler = Callable[..., Awaitable[None]]


class MessageRouter:
    """Keep operator and controller permissions independent of JSON parsing."""

    def __init__(self):
        self._handlers: dict[type[BaseMsg], Handler] = {}

    def register(self, msg_type: type[BaseMsg], handler: Handler) -> None:
        self._handlers[msg_type] = handler

    def get(self, msg: BaseMsg) -> Handler | None:
        return self._handlers.get(type(msg))
