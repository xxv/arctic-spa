"""Arctic Spa hot tub interface"""

import socket
import time
import struct
from enum import IntEnum
from arctic_spa.proto import arctic_spa_pb2


class TypeKey(IntEnum):
    """Packet type keys"""
    LIVE = 0
    SETTINGS = 2
    CONFIG = 3
    PEAK = 4
    CLOCK = 5
    INFO = 6
    ERROR = 7
    FIRMWARE = 8
    UNKNOWN_10 = 10
    FILTERS = 13
    ONZEN_LIVE = 48
    ONZEN_SETTINGS = 50
    LPC_LIVE = 112
    LPC_INFO = 114
    LPC_CONFIG = 115
    LPC_PREFERENCES = 116
    LPC_LIGHTS = 117
    LPC_SCHEDULE = 118
    LPC_PEAK_DEVICES = 119
    LPC_ERROR = 121


class Packet():
    """A packet, including a type and payload
    
    This is not a TCP/IP packet, but a contiguous message to/from the controller."""

    preamble = b"\xAB\xAD\x1D\x3A"

    def __init__(
        self, data_type: TypeKey, counter: int, checksum: bytes, payload: bytes
    ) -> None:
        self.data_type = data_type
        self.counter = counter
        self.checksum = checksum
        self.payload = payload
        self.data = self._load_from_network(payload)

    def _load_from_network(self, payload):
        raise NotImplementedError

    def __str__(self):
        return f"<{self.data_type.name} counter: {self.counter}, " \
                "checksum: {self.checksum}> payload:\n{self.data}\nend payload"


class Live(Packet):
    """Live stats"""
    def __init__(self, counter: int, checksum: bytes, payload: bytes) -> None:
        super().__init__(TypeKey.LIVE, counter, checksum, payload)

    def _load_from_network(self, payload):
        live = arctic_spa_pb2.SpaLive()
        live.ParseFromString(payload)

        return live


class Config(Packet):
    """Product configuration"""
    def __init__(self, counter: int, checksum: bytes, payload: bytes) -> None:
        super().__init__(TypeKey.CONFIG, counter, checksum, payload)

    def _load_from_network(self, payload):
        parsed = arctic_spa_pb2.Config()
        parsed.ParseFromString(payload)

        return parsed


class Info(Packet):
    """Technical information"""
    def __init__(self, counter: int, checksum: bytes, payload: bytes) -> None:
        super().__init__(TypeKey.INFO, counter, checksum, payload)

    def _load_from_network(self, payload):
        parsed = arctic_spa_pb2.Info()
        parsed.ParseFromString(payload)

        return parsed


class OnzenLive(Packet):
    """Live information from the Onzen system"""
    def __init__(self, counter: int, checksum: bytes, payload: bytes):
        super().__init__(TypeKey.ONZEN_LIVE, counter, checksum, payload)

    def _load_from_network(self, payload):
        live = arctic_spa_pb2.OnzenLive()
        live.ParseFromString(payload)

        return live


class DecodeError(Exception):
    """An error decoding the packet"""
    def __init__(self, message):
        super().__init__(message)


class SpaProtocol(object):
    """Spa network protocol decoder"""
    type_map = {
        TypeKey.LIVE: Live,
        TypeKey.CONFIG: Config,
        TypeKey.INFO: Info,
        TypeKey.ONZEN_LIVE: OnzenLive,
    }

    def decode(self, data: bytes) -> list[Packet]:
        """Decode the data into a list of packets"""
        packets = []

        to_decode = data

        while len(to_decode) > 0:
            (packet, remainder) = self.decode_one(to_decode)
            packets.append(packet)

            to_decode = remainder

        return packets

    def decode_one(self, data: bytes) -> tuple[Packet, bytes]:
        """Decode the first packet of data and return any undecoded data"""
        header = struct.unpack("!xxxxBBBBIIHH", data[0:20])
        data_type = TypeKey(header[6])
        length = header[7]
        payload = data[20 : (20 + length)]

        packet = None

        if data_type != TypeKey.UNKNOWN_10:
            if data[0:4] != Packet.preamble:
                raise DecodeError("Data does not start with preamble")

            checksum = bytes(header[0:4])
            counter = header[4]
            if data_type in self.type_map:
                packet = self.type_map[data_type](counter, checksum, payload)

        remainder = data[20 + length :]

        return (packet, remainder)
    
    def _debug(self, checksum, counter, data_type, length, payload):
        print(f"checksum: {checksum[0]:0X}{checksum[1]:0X}{checksum[2]:0X}{checksum[3]:0X}")
        print(f"counter: {counter}")
        print(f"data_type: {data_type.name}")
        print(f"length: {length}")

        if len(payload) == length:
            print("Payload length matches")
        else:
            print("Payload length does not match")

        print("Payload:")
        print("-" * 70)


class ArcticSpa():
    """Interface for communicating with Arctic Spa hot tubs"""
    PORT = 65534

    INIT = (
        b"\x00\xab\xad\x1d\x3a\x11\xc2\xc9\x84\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\xab\xad\x1d\x3a\x35\xa9\x2c\x14\x00\x00\x00\x00\x00\x00\x00\x00\x00\x30\x00\x00"
    )

    def __init__(self, host: str) -> None:
        """Configures a new"""
        self.host = host
        self.proto = SpaProtocol()

    def poll(self, desired_types=(Live, OnzenLive)) -> list:
        """Connects, requests the desired types of data, and disconnects
        
        This looks for a set of desired packets and returns the most recent of each type.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((self.host, ArcticSpa.PORT))
            sock.sendall(ArcticSpa.INIT)

            got_data = False
            desired_packets = {}
            for desired_type in desired_types:
                desired_packets[desired_type] = None

            while not got_data:
                data = sock.recv(4096)

                packets = self.proto.decode(data)
                for packet in packets:
                    desired_packets[type(packet)] = packet
                
                got_data = True
                if None in desired_packets.values():
                    got_data = False

                time.sleep(0.1)

            return desired_packets.values()

    def connect(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.host, ArcticSpa.PORT))
            s.sendall(ArcticSpa.INIT)

            while True:
                data = s.recv(4096)

                self.proto.decode(data)

                time.sleep(0.1)
