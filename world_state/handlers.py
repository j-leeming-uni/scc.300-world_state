import os
import selectors
import socket
import sys

import serial

from .comms import StreamHandler


def handle_request(request: bytes, world_state: dict[bytes, bytes]):
    if not request:
        return
    if b'\n' in request:
        responses = []
        for line in request.split(b'\n'):
            response = handle_request(line, world_state)
            if response:
                responses.append(response)
        if not responses:
            return None
        return b'\n'.join(responses) + b'\n'

    try:
        mode, register, *data = request.split(b' ')
    except ValueError:
        if request == b'SHOW':
            lines = []
            for register, data in world_state.items():
                line = f'{register} = {data}  [{data.hex()}]'
                lines.append(line)
            return b'\n'.join(l.encode() for l in lines) + b'\n'
        print(f'Invalid request: {request}')
        return
    match mode:
        case b'GET':
            if register in world_state:
                return b'Y' + world_state[register] + b'\n'
            else:
                return b'X\n'
        case b'SET':
            world_state[register] = b''.join(data)
        case b'DEL':
            if register in world_state:
                del world_state[register]
        case _:
            print(f'Unknown mode: {mode}')


class StdinStreamHandler(StreamHandler):
    def fileno(self):
        return sys.stdin.fileno()

    def on_ready(self, world_state: dict[bytes, bytes]):
        request = sys.stdin.readline().strip().encode()
        response = handle_request(request, world_state)
        if response:
            sys.stdout.buffer.write(response)
            sys.stdout.buffer.flush()

    def connect(self):
        pass

    def disconnect(self):
        pass


class SerialStreamHandler(StreamHandler):
    def __init__(self, serial_port, baud_rate=115200):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.ser = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        try:
            self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            print(f"Connected to serial://{self.serial_port}:{self.baud_rate}")
        except serial.SerialException as e:
            print(f"Error: {e}")

    def disconnect(self):
        if self.ser:
            self.ser.close()
            print(f"Disconnected from serial://{self.serial_port}:{self.baud_rate}")
        else:
            print("No active serial connection to close.")

    def fileno(self):
        return self.ser.fileno()

    def on_ready(self, world_state):
        request = self.ser.readline().strip()
        response = handle_request(request, world_state)
        if response:
            self.ser.write(response)
            self.ser.flush()


class SocketHandler(StreamHandler):
    def __init__(self, server: socket.socket, address):
        self.server = server
        self.address = address
        self.selector = None
        self.clients = []

    def fileno(self):
        return self.server.fileno()

    def on_ready(self, world_state):
        client, address = self.server.accept()
        client.setblocking(False)
        handler = SocketClientHandler(self, client)
        handler.connect()
        handler.bind(self.selector)
        self.clients.append(handler)

    def connect(self):
        self.server.setblocking(False)
        self.server.bind(self.address)
        self.server.listen(5)
        print(f'Listening on uds://{self.address}')

    def disconnect(self):
        for client in self.clients:
            client.disconnect()
        self.server.close()
        os.remove(self.address)
        print(f'Closed uds://{self.address}')

    def bind(self, selector: selectors.BaseSelector):
        self.selector = selector
        selector.register(self, selectors.EVENT_READ)

    def unbind(self, selector: selectors.BaseSelector):
        for client in self.clients:
            client.unbind(selector)
        selector.unregister(self)

    def remove_client(self, client):
        self.clients.remove(client)
        client.unbind(self.selector)


class SocketClientHandler(StreamHandler):
    def __init__(self, server: SocketHandler, client: socket.socket):
        self.server = server
        self.client = client

    def fileno(self):
        return self.client.fileno()

    def on_ready(self, world_state):
        try:
            request = self.client.recv(1024)
        except ConnectionResetError:
            request = None
        if not request:
            self.server.remove_client(self)
            self.disconnect()
            return
        request = request.strip()
        response = handle_request(request, world_state)
        if response:
            try:
                self.client.send(response)
            except BrokenPipeError:
                self.server.remove_client(self)
                self.disconnect()
            except BlockingIOError:
                pass

    def connect(self):
        self.client.setblocking(False)

    def disconnect(self):
        self.client.close()
