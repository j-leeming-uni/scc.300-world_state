import selectors
from abc import ABC, abstractmethod


class StreamHandler(ABC):
    @abstractmethod
    def fileno(self):
        raise NotImplementedError()

    @abstractmethod
    def on_ready(self, world_state):
        pass

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    def bind(self, selector: selectors.BaseSelector):
        selector.register(self, selectors.EVENT_READ)

    def unbind(self, selector: selectors.BaseSelector):
        selector.unregister(self)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class CommunicationsManager:
    def __init__(self, *handlers: StreamHandler):
        self.handlers = handlers
        self.selector = selectors.DefaultSelector()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        for handler in self.handlers:
            handler.connect()
            handler.bind(self.selector)

    def disconnect(self):
        for handler in self.handlers:
            handler.unbind(self.selector)
            handler.disconnect()

    def poll(self, world_state):
        for key, mask in self.selector.select():
            handler = key.fileobj
            handler.on_ready(world_state)
