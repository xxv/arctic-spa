# Arctic Spa Hot Tub library

This library talks to Arctic Spa brand hot tubs and reports sensor information.

As of this initial library version, this only supports polling the hot tub for
status information, not controlling it.

## Overview

To request status information from the hot tub, create an `ArcticSpa` object with
the device's hostname and call `poll()`:

```
import asyncio
from arctic_spa import ArcticSpa

spa = ArcticSpa('192.168.123.42')
packets = asyncio.run(spa.poll())
```

`packets` is a list of the latest packets received by the network client. `poll()` will
return once all the requested types have been returned. Currently this only supports
requesting `Live` and `OnzenLive` packet types, but may return other types if the hot tub
sends them in addition to the requested packets.

See [network.py](example/network.py) for a complete example.

## Network Discovery

You can search the local subnet for a hot tub. To do so, provide the local
address of the calling code and the subnet mask you'd like it to scan:

```
searcher = NetworkSearch(local_addr, subnet_mask)
results = asyncio.run(searcher.search())
```

`results` is a list of all the discovered devices (empty if there are none).

See [network.py](example/network.py) for a complete example.

## License

Copyright (c) 2022 Steve Pomeroy <steve@staticfree.info>

This is licensed under the Apache 2.0 software license.

## Disclaimer

This library is neither endorsed nor sponsored by Arctic Spa. By using this
library, you agree to take full responsibilty for any actions that may occur
from the use of this library.

That said, we love our Arctic Spa hot tub and don't want to damage it, so we try
very hard to not do anything risky with it.
