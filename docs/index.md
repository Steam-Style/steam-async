# Steam Python Documentation

Welcome to the documentation for the Steam Python project. This library provides a fast and lightweight Python interface for interacting with Steam.

!!! warning

    `steam-python` is currently under heavy development and is not yet ready for public use.

## Getting Started

To get started, check out the [API Reference](reference.md) to see the available classes and methods.

## Installation

You can install the library through our official GitHub repository.

```
pip install git+https://github.com/Steam-Style/steam-python
```

## Usage Example

To interact with Steam you must first connect to a Connection Manager Server and then log in. Below is an example for retrieving app information for Steam applications.

```python
import asyncio
from steam.client import SteamClient

async def main():
    client = SteamClient()

    try:
        # Connect to Steam
        await client.connect()

        # Login anonymously
        await client.anonymous_login()

        # Get product info for TF2, Dota 2, and CS2
        product_info = await client.get_product_info([440, 570, 730])

        if product_info:
            for app_id, parsed_vdf in product_info.items():
                print(app_id, parsed_vdf["appinfo"]["common"]["name"])

    finally:
        # Disconnect
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```
