#!/usr/bin/env python3

import asyncio
import sys
from arctic_spa import ArcticSpa, Live, OnzenLive


def main():
    host = sys.argv[1]
    spa = ArcticSpa(host)

    packets = asyncio.run(spa.poll())

    for packet in packets:
        print(f'Packet: {packet}, data:\n{packet.data}')

        if isinstance(packet, Live):
            print(f'Temperature(F): {packet.temperature_fahrenheit}')
        elif isinstance(packet, OnzenLive):
            print(f'pH: {packet.ph_100/100:.02f}')


if __name__ == '__main__':
    main()
