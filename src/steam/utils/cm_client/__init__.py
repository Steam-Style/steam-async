import aiohttp
import asyncio
import time
import logging
import struct
import random
from typing import Optional, Any, cast
from google.protobuf.message import Message
from steam.enums.emsg import EMsg
from steam.utils.protobuf_manager import ProtobufManager
from steam.utils.protobuf_manager.protobufs.steammessages_base_pb2 import CMsgProtoBufHeader  # type: ignore
from steam.enums.common import EResult
from .constants import (
    STEAM_CM_LIST_URL,
    MAGIC_HEADER,
    CONNECTION_TIMEOUT,
    MAX_CONNECTIONS
)
from steam.utils.crypto import (
    symmetric_encrypt,
    symmetric_encrypt_HMAC,
    symmetric_decrypt,
    symmetric_decrypt_HMAC
)
from steam.utils.handshake import perform_handshake
from steam.utils.event_emitter import EventEmitter
from steam.utils.packet import SteamPacket


class CMClient(EventEmitter):
    """
    Manages connections to Steam Connection Manager servers.
    """

    _log: logging.Logger = logging.getLogger(__name__)

    def __init__(self):
        """
        Initializes the CMClient.
        """
        super().__init__()
        self.session: Optional[aiohttp.ClientSession] = None
        self.server_list: list[tuple[str, int]] = []
        self.fastest_server: tuple[Optional[tuple[str, int]], float] = (
            None, float("inf"))
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected: bool = False
        self.session_key: Optional[bytes] = None
        self.hmac_secret: Optional[bytes] = None
        self.steam_id: int = 0
        self.session_id: int = random.randint(1, 2**31 - 1)
        self._loop_task: Optional[asyncio.Task[Any]] = None

    async def _test_server_latency(self, host: str, port: int) -> float:
        try:
            start_time = time.time()
            future = asyncio.open_connection(host, port)
            _, writer = await asyncio.wait_for(future, timeout=CONNECTION_TIMEOUT)

            latency = time.time() - start_time
            writer.close()
            await writer.wait_closed()

            return latency

        except (asyncio.TimeoutError, OSError, ValueError):
            return float("inf")

    async def _find_fastest_server(self) -> tuple[Optional[tuple[str, int]], float]:
        semaphore = asyncio.Semaphore(MAX_CONNECTIONS)

        async def bounded_test(host: str, port: int) -> float:
            async with semaphore:
                return await self._test_server_latency(host, port)

        tasks = [bounded_test(host, port) for (host, port) in self.server_list]
        latencies = await asyncio.gather(*tasks)
        fastest_server = (None, float("inf"))

        for (server_ip), latency in zip(self.server_list, latencies):
            if latency < fastest_server[1]:
                fastest_server = (server_ip, latency)

        self.fastest_server = fastest_server
        return fastest_server

    async def get_server_list(self) -> list[tuple[str, int]]:
        """
        Fetches a list of available servers.

        Returns:
            A list of tuples containing server host and port.
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()

        try:
            async with self.session.get(STEAM_CM_LIST_URL) as response:
                response.raise_for_status()
                json_data = await response.json()
                raw_server_list = json_data.get(
                    "response", {}).get("serverlist", [])
                self.server_list = []

                for server_ip in raw_server_list:
                    host, port = server_ip.split(':')
                    port = int(port)
                    self.server_list.append((host, port))

                return self.server_list
        except aiohttp.ClientError as e:
            self._log.error(f"Failed to fetch server list: {e}")
            return []

    async def connect(self, retry: bool = False, use_fastest: bool = False) -> EResult:
        """
        Connects to a server.

        Args:
            retry: If True, retries connecting if the initial connection attempt fails.
            use_fastest: If True, determines and connects to the server with the lowest latency.
                This adds initial overhead but may improve connection speed.

        Returns:
            EResult.OK if connection is successful, EResult.ConnectFailed otherwise.
        """
        while True:
            server = await self._select_server(use_fastest)

            if not server:
                return EResult.ConnectFailed

            host, port = server

            try:
                self.reader, self.writer = await asyncio.open_connection(host, port)
            except (OSError, ValueError, TimeoutError) as e:
                self._log.error(
                    f"Failed to connect to server {host}:{port}: {e}")

                if not retry:
                    return EResult.ConnectFailed

                continue

            if await self._handshake():
                self.connected = True
                self._loop_task = asyncio.create_task(self._read_loop())
                return EResult.OK

            await self.disconnect()

            if not retry:
                return EResult.ConnectFailed

            self._log.info("Retrying connection...")

    async def _read_loop(self):
        while self.connected:
            message = await self.listen()

            if message:
                try:
                    packet = SteamPacket.parse(message)
                    if packet.emsg == EMsg.Multi:
                        for sub_packet in packet.unpack_multi():
                            self.emit(sub_packet.emsg, sub_packet)
                    else:
                        self.emit(packet.emsg, packet)
                except Exception as e:
                    self._log.error(f"Error parsing packet: {e}")
            else:
                if self.connected:
                    self._log.warning("Connection lost in read loop")
                    await self.disconnect()

                break

    async def _select_server(self, use_fastest: bool) -> Optional[tuple[str, int]]:
        if not self.server_list:
            await self.get_server_list()

        if use_fastest or self.fastest_server[0] is not None:
            if self.fastest_server[0] is None:
                await self._find_fastest_server()

            return self.fastest_server[0]

        for host, port in self.server_list:
            if await self._test_server_latency(host, port) < float("inf"):
                return (host, port)

        await self.get_server_list()

        for host, port in self.server_list:
            if await self._test_server_latency(host, port) < float("inf"):
                return (host, port)

        return None

    async def _handshake(self) -> bool:
        return await perform_handshake(self)

    async def disconnect(self):
        """
        Disconnects from the current server.
        """
        self.connected = False

        if self._loop_task:
            self._loop_task.cancel()

            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

            self._loop_task = None

        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass

            self.writer = None
            self.reader = None

        if self.session:
            await self.session.close()
            self.session = None

    async def send_protobuf_message(self, emsg: EMsg, message: Message, steam_id: Optional[int] = None):
        """
        Sends a protobuf message to the server.

        Args:
            emsg: The EMsg identifier for the message.
            message: The protobuf message to send.
            steam_id: Optional Steam ID to include in the message header.
        """
        if not self.connected:
            self._log.error("The client is not connected")
            return

        header = cast(Any, CMsgProtoBufHeader())
        header.steamid = steam_id if steam_id is not None else self.steam_id
        header.client_sessionid = self.session_id

        header_data = header.SerializeToString()
        body_data = message.SerializeToString()

        emsg_id = ProtobufManager.add_mask(emsg)
        data = struct.pack("<I", emsg_id)
        data += struct.pack("<I", len(header_data))
        data += header_data
        data += body_data

        await self.send(data)

    async def send(self, data: bytes) -> bool:
        """
        Sends data to the connected server.

        Args:
            data: The data to send as bytes.

        Returns:
            True if the data was sent successfully, False otherwise.
        """
        if not self.writer:
            self._log.warning("The client is not connected")
            return False

        if self.session_key:
            if self.hmac_secret:
                data = symmetric_encrypt_HMAC(
                    data, self.session_key, self.hmac_secret)
            else:
                data = symmetric_encrypt(data, self.session_key)

        try:
            self.writer.write(len(data).to_bytes(
                4, byteorder="little") + MAGIC_HEADER.encode() + data)
            await self.writer.drain()
            return True

        except Exception as e:
            self._log.error(f"Error sending data: {e}")
            return False

    async def listen(self) -> Optional[bytes]:
        """
        Listens for incoming messages from the server.

        Returns:
            The received message as bytes, or None if an error occurs.
        """
        if not self.reader:
            self._log.warning("Not connected")
            return None

        try:
            length_data = await self.reader.readexactly(4)
            length = int.from_bytes(length_data, byteorder="little")
            magic_header = await self.reader.readexactly(4)

            if magic_header != MAGIC_HEADER.encode():
                self._log.warning("Invalid magic header, disconnecting")
                return None

            message = await self.reader.readexactly(length)

            if self.session_key:
                if self.hmac_secret:
                    message = symmetric_decrypt_HMAC(
                        message, self.session_key, self.hmac_secret)
                else:
                    message = symmetric_decrypt(message, self.session_key)

            return message

        except asyncio.IncompleteReadError:
            self._log.warning("Server closed connection")
            return None
        except Exception as e:
            self._log.error(f"Error listening: {e}")
            return None
