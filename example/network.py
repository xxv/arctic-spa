#!/usr/bin/env python3

import sys
from arctic_spa import ArcticSpa


def main():
    host = sys.argv[1]
    spa = ArcticSpa(host)
    packets = spa.poll()
    
    for packet in packets:
        print(f'Packet: {packet}, data:\n{packet.data}')


if __name__ == '__main__':
    main()
