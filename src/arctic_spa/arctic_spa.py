"""Arctic Spa hot tub interface"""

import asyncio
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
    HEARTBEAT = 10
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

    def __getattr__(self, __name: str) -> any:
        return getattr(self.data, __name)

    def __str__(self):
        return f"<{self.data_type.name} counter: {self.counter}, " \
                f"checksum: {self._checksum_str()}> payload:\n{self.data}\nend payload"

    def _checksum_str(self):
        return "".join(map(lambda digit: f'{digit:0X}', self.checksum))


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


class SpaProtocol:
    """Spa network protocol decoder"""
    TYPE_MAP = {
        TypeKey.LIVE: Live,
        TypeKey.CONFIG: Config,
        TypeKey.INFO: Info,
        TypeKey.ONZEN_LIVE: OnzenLive,
    }

    HEADER_SIZE = 20

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

        if len(data) < self.HEADER_SIZE:
            raise DecodeError(f"Expecting at least {self.HEADER_SIZE} bytes, got {len(data)}")

        if data[0:4] != Packet.preamble:
            raise DecodeError("Data does not start with preamble")

        header = struct.unpack("!xxxxBBBBIIHH", data[0:self.HEADER_SIZE])

        data_type = TypeKey(header[6])
        length = header[7]
        payload = data[self.HEADER_SIZE : (self.HEADER_SIZE + length)]

        packet = None

        if data_type != TypeKey.HEARTBEAT:
            checksum = bytes(header[0:4])
            counter = header[4]

            if data_type in self.TYPE_MAP:
                packet = self.TYPE_MAP[data_type](counter, checksum, payload)

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

    _REQUEST_LIVE = \
        b"\xab\xad\x1d\x3a\x11\xc2\xc9\x84\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    _REQUEST_ONZEN_LIVE = \
        b"\xab\xad\x1d\x3a\x35\xa9\x2c\x14\x00\x00\x00\x00\x00\x00\x00\x00\x00\x30\x00\x00"

    _INIT = _REQUEST_LIVE + _REQUEST_ONZEN_LIVE

    def __init__(self, host: str) -> None:
        """Configures a new client

        This client can be used in two ways:
           * Calling `poll()` will connect, get the data, and disconnect automatically.
           * Calling `connect()`, `read_packets()`, and `disconnect()` lets you read
             as many packets as you want."""
        self.host = host
        self.proto = SpaProtocol()
        self._reader = None
        self._writer = None

    async def poll(self, types=(Live, OnzenLive), timeout=5) -> list:
        """Connects, requests the desired types of data, and disconnects

        This looks for a set of desired packets and returns the most recent of each type.
        This waits until all the requested types have been returned.

        Note: this may return packet types that were not requested in addition to the requested
        types.
        """
        return await asyncio.wait_for(self._poll_no_timeout(desired_types=types), timeout)

    async def _poll_no_timeout(self, desired_types) -> list:
        await self.connect()

        got_data = False
        desired_packets = {}
        for desired_type in desired_types:
            desired_packets[desired_type] = None

        while not got_data:
            for packet in await self.read_packets():
                if packet is not None:
                    desired_packets[type(packet)] = packet

            got_data = True
            if None in desired_packets.values():
                got_data = False

        await self.disconnect()

        return desired_packets.values()

    async def connect(self) -> None:
        """Connects to the hot tub and transmits an init sequence"""
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()

        reader, writer = await asyncio.open_connection(self.host, ArcticSpa.PORT)
        self._reader = reader
        self._writer = writer

        writer.write(ArcticSpa._INIT)
        await writer.drain()

    async def disconnect(self) -> None:
        """Disconnects the client"""
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()

            self._writer = None
            self._reader = None

    async def read_packets(self) -> list[Packet]:
        """Reads from the network and returns any received packets"""
        if self._reader is None:
            raise ConnectionError("Not connected")

        data = await self._reader.read(4096)

        return self.proto.decode(data)
