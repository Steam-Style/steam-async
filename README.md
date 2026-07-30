# Steam Async Python

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/Steam-Style)](https://github.com/sponsors/Steam-Style)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org/downloads/)
[![Documentation](https://img.shields.io/badge/Docs-brightgreen?link=https%3A%2F%2Fpython.steam.style)](https://python.steam.style)

A fast and lightweight Python interface for interacting with Steam asynchronously using [asyncio](https://docs.python.org/3/library/asyncio.html). Largely inspired by [Valve Python's Steam package](https://github.com/ValvePython/steam) and [the fork by Solstice Game Studios](https://github.com/solsticegamestudios/steam), this library introduces various tweaks to modernize and improve the structure, including complete typing support and modern dependencies. Some logic is also taken from [SteamRE's SteamKit](https://github.com/SteamRE/SteamKit).

> [!IMPORTANT]
>
> `steam-async` is currently under heavy development and is not yet ready for public use.

## Installation

```bash
pip install git+https://github.com/Steam-Style/steam-async
```

## Usage

To interact with Steam you must first connect to a connection manager server and then log in.

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

        # ...

    finally:
        # Disconnect
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Development

This project uses uv for Python dependency management.

1. Prerequisites

   Install `uv` if you haven't already.

   ```bash
   # Linux/macOS
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. Setup the project:

   Clone the repository and sync the dependencies. uv will automatically download the correct Python version and create a virtual environment for you:

   ```bash
   git clone https://github.com/Steam-Style/steam-async.git
   cd steam-async
   uv sync --all-groups
   uv build
   ```

---

<div align="center">

[![GitHub Stars](https://img.shields.io/github/stars/Steam-Style/steam-async?style=social)](https://github.com/Steam-Style/steam-async/stargazers)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/Steam-Style?style=social)](https://github.com/sponsors/Steam-Style)

Made with ❤️ by the Steam Style team

[Report an Issue](https://github.com/Steam-Style/steam-async/issues) • [Visit Steam Style](https://steam.style)

</div>
