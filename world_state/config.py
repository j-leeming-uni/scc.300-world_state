from __future__ import annotations

import socket
import tomllib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .comms import StreamHandler
from .handlers import SerialStreamHandler, SocketHandler


def load(path: str | Path):
    path = Path(path)
    with path.open('rb') as f:
        raw_config = tomllib.load(f)
    return Config.parse(raw_config)


@dataclass
class Config:
    nodes: list[Node]
    scripts: Optional[Scripts]

    @classmethod
    def parse(cls, raw_config: dict) -> Config:
        return cls(
            nodes=[Node.parse(raw_node) for raw_node in raw_config['node'] if raw_node.get('enabled', True)],
            scripts=Scripts.parse(raw_config.get('scripts'))
        )


@dataclass
class Scripts:
    startup: Optional[str]

    @classmethod
    def parse(cls, raw_scripts: Optional[dict]) -> Optional[Scripts]:
        if raw_scripts is None:
            return None
        return cls(startup=raw_scripts.get('startup'))


@dataclass
class Node(ABC):
    name: str

    @abstractmethod
    def get_handler(self) -> StreamHandler:
        pass

    @classmethod
    def parse(cls, raw_node: dict) -> Node:
        if 'serial' in raw_node:
            return SerialNode.parse(raw_node)
        elif 'socket' in raw_node:
            return UDSNode.parse(raw_node)
        raise ValueError(f"Unknown node type: {raw_node}")


@dataclass
class SerialNode(Node):
    port: str
    baud_rate: int

    def get_handler(self) -> StreamHandler:
        return SerialStreamHandler(self.port, self.baud_rate)

    @classmethod
    def parse(cls, raw_node: dict) -> SerialNode:
        return cls(
            name=raw_node['name'],
            port=raw_node['serial'],
            baud_rate=raw_node['baud']
        )


@dataclass
class UDSNode(Node):
    path: str

    def get_handler(self) -> StreamHandler:
        return SocketHandler(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM), self.path)

    @classmethod
    def parse(cls, raw_node: dict) -> UDSNode:
        return cls(
            name=raw_node['name'],
            path=raw_node['socket'],
        )
