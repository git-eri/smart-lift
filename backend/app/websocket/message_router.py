from typing import Callable, Dict, Type
from app.models.messages import BaseMsg

Handler = Callable[..., object]


class MessageRouter:
    def __init__(self):
        self._handlers: Dict[Type[BaseMsg], Handler] = {}

    def register(self, msg_type: Type[BaseMsg], handler: Handler):
        self._handlers[msg_type] = handler

    def get(self, msg: BaseMsg):
        return self._handlers.get(type(msg))