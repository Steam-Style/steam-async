# Steam Async Python Documentation

Welcome to the documentation for the `steam-async` Python project. This library provides a fast and lightweight Python interface for interacting with Steam asynchronously using [asyncio](https://docs.python.org/3/library/asyncio.html).

!!! warning

    `steam-async` is currently under heavy development and is not yet ready for public use.

## Getting Started

To get started, check out the [API Reference](reference.md) to see the available classes and methods.

## Installation

You can install the library through our official GitHub repository.

```
pip install git+https://github.com/Steam-Style/steam-async
```

## Usage Example

To interact with Steam you must first connect to a connection manager server and then log in. Below is an example for retrieving app information for Steam applications.

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
        apps = product_info.get("apps", {}) if product_info else {}

        for app_id, app in apps.items():
            print(app_id, app["common"]["name"])

    finally:
        # Disconnect
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```
