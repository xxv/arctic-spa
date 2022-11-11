"""Arctic Spa network discovery

This will do a UDP probe of all the devices on the given network to
determine if any of them are an Arctic Spa device.

```
searcher = NetworkSearch('192.168.100.5', 24)
```

"""
import asyncio as aio
import ipaddress
from collections.abc import Callable


class UdpDiscoverProtocol(aio.DatagramProtocol):
    """Calls found_host with a host when a device is detected"""
    def __init__(self, found_host: Callable[[str], None]) -> None:
        self._found_host = found_host

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if data.startswith(NetworkSearch.RESPONSE):
            self._found_host(addr[0])


class NetworkSearch:
    """Searches the network for an Arctic Spa device

This will do a UDP probe of all the devices on the given network to
determine if any of them are an Arctic Spa device.

Provide the local IP address of the scanning machine and the subnet
```
searcher = NetworkSearch('192.168.100.5', 24)
results = asyncio.run(searcher.search())

print(f'Found {len(results)} devices')
```
    """
    QUERY_PORT = 9131
    RESPONSE_PORT = 33327
    QUERY = b"Query,BlueFalls,"
    RESPONSE = b"Response,BlueFalls,"

    def __init__(self, ip_address: str, netmask: int) -> None:
        self._ip_address = ip_address
        self._network = ipaddress.ip_network(f'{ip_address}/{netmask}', strict=False)
        self._responses = []

    async def search(self) -> list:
        """Search the network for any devices and return a list of IP addresses"""
        return await self._run_scanner(self._ip_address, self._scan)

    def _found_host(self, addr: str) -> None:
        self._responses.append(addr)

    async def _check_host(self, transport: aio.DatagramTransport, host: str) -> bool:
        """Return True if the host responds to the query"""
        transport.sendto(self.QUERY, (host, self.QUERY_PORT))
        await aio.sleep(1)

        return host in self._responses

    async def _run_scanner(self, addr: str, scanner: Callable[[aio.DatagramTransport], None]) -> list:
        self._responses = []
        loop = aio.get_running_loop()

        transport, _ = await loop.create_datagram_endpoint(
            lambda: UdpDiscoverProtocol(self._found_host),
            local_addr=(addr, self.RESPONSE_PORT)
            )

        try:
            await scanner(transport)
        finally:
            transport.close()

        return self._responses

    async def _scan(self, transport: aio.DatagramTransport) -> None:
        tasks = []

        for host in self._network.hosts():
            tasks.append(aio.create_task(self._check_host(transport, str(host))))

        await aio.gather(*tasks)
