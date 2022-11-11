#!/usr/bin/env python3

import asyncio
import socket
import sys
from arctic_spa import ArcticSpa, Live, OnzenLive, NetworkSearch
from arctic_spa.proto.arctic_spa_pb2 import SpaLive as SpaLivePB, OnzenLive as OnzenLivePB


def get_ip() -> str:
    """Get the local address with the default route

    From fatal_error on Stack Overflow https://stackoverflow.com/a/28950776"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0)
    try:
        # doesn't even have to be reachable
        sock.connect(('10.254.254.254', 1))
        ip_addr = sock.getsockname()[0]
    except Exception:
        ip_addr = '127.0.0.1'
    finally:
        sock.close()

    return ip_addr

def find_hot_tub(local_addr: str, subnet_mask: int) -> str:
    """Scan the subnet for Arctic Spa hot tubs"""
    print(f'Searching for hot tub from {local_addr}/{subnet_mask}...')
    searcher = NetworkSearch(local_addr, subnet_mask)
    results = asyncio.run(searcher.search())

    host = None

    if len(results) >= 1:
        if len(results) > 1:
            print('Multiple hot tubs found! :o Using the first.')
        host = results[0]
        print(f'Found a hot tub at {host}! :D')
    else:
        print('No hot tubs found :(')

    return host

def main():
    host = None
    if len(sys.argv) == 1:
        host = find_hot_tub(get_ip(), 24)

        if not host:
            return

    elif len(sys.argv) == 2:
        host = sys.argv[1]

    spa = ArcticSpa(host)

    print(f'Polling {host}...')
    packets = asyncio.run(spa.poll())

    for packet in packets:
        if isinstance(packet, Live):
            print(f'Temperature(F): {packet.temperature_fahrenheit}')
            print(f'Pump 1: {SpaLivePB.PumpStatus.Name(packet.pump_1)}')
            print(f'Heater 1: {SpaLivePB.HeaterStatus.Name(packet.heater_1)}')
        elif isinstance(packet, OnzenLive):
            print(f'pH: {packet.ph_100/100:.02f}')
            print(f'pH color: {OnzenLivePB.Color.Name(packet.ph_color)}')


if __name__ == '__main__':
    main()
