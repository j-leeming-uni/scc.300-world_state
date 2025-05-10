import sys
import time
from pprint import pprint

import serial

from world_state import config
from world_state.comms import CommunicationsManager
from world_state.handlers import StdinStreamHandler, handle_request

if len(sys.argv) < 2:
    print('USAGE: python3 SCRIPT CONFIG_FILE')
    exit(-1)

config_file = config.load(sys.argv[1])
pprint(config_file)

try:
    world_state = {}

    if config_file.scripts is not None:
        if config_file.scripts.startup is not None:
            with open(config_file.scripts.startup, 'rb') as f:
                for line in f:
                    handle_request(line.strip(), world_state)

    # Create a serial connection
    with CommunicationsManager(StdinStreamHandler(), *[node.get_handler() for node in config_file.nodes]) as manager:
        print("Connecting...")
        time.sleep(1)  # Wait for the connection to establish
        print("Ready")

        # Continuously check for incoming messages from serial and stdin
        while True:
            manager.poll(world_state)

except serial.SerialException as e:
    print(f"Error: {e}")
except KeyboardInterrupt:
    print("Program interrupted.")
