import asyncio
import binascii
import itertools
import logging
import random
import struct
import time
from typing import Any

import aiohttp
from google.protobuf.message import Message

from steam.enums.common import EResult
from steam.enums.emsg import EMsg
from steam.utils.crypto import (
    generate_session_key,
    symmetric_decrypt,
    symmetric_decrypt_HMAC,
    symmetric_encrypt,
    symmetric_encrypt_HMAC,
)
from steam.utils.event_emitter import EventEmitter
from steam.utils.packet import SteamPacket
from steam.utils.protobuf_manager import ProtobufManager
from steam.utils.protobuf_manager.protobufs.steammessages_base_pb2 import (
    CMsgProtoBufHeader,
)
from steam.utils.structs import (
    MsgChannelEncryptRequest,
    MsgChannelEncryptResponse,
    MsgHdr,
)

STEAM_CM_LIST_URL = (
    "https://api.steampowered.com/ISteamDirectory/GetCMList/v1/?cellid=0"
)
MAGIC_HEADER = "VT01"
CONNECTION_TIMEOUT = 5


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
        self.session: aiohttp.ClientSession | None = None
        self.server_list: list[tuple[str, int]] = []
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.connected: bool = False
        self.session_key: bytes | None = None
        self.hmac_secret: bytes | None = None
        self.steam_id: int = 0
        self._global_job_id: itertools.count = itertools.count(1)
        self._session_id: int = random.randint(1, 2**31 - 1)
        self._loop_task: asyncio.Task[Any] | None = None

    async def _test_server_latency(self, host: str, port: int) -> float | None:
        try:
            start_time = time.time()
            future = asyncio.open_connection(host, port)
            _, writer = await asyncio.wait_for(future, timeout=CONNECTION_TIMEOUT)

            latency = time.time() - start_time
            writer.close()
            await writer.wait_closed()

            return latency

        except (asyncio.TimeoutError, OSError, ValueError):
            return None

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
                    host, port = server_ip.split(":")
                    port = int(port)
                    self.server_list.append((host, port))

                return self.server_list
        except aiohttp.ClientError as e:
            self._log.error("Failed to fetch server list: %s", e)
            return []

    async def connect(
        self,
        host: str | None = None,
        port: int | None = None,
        retry: bool = False,
    ) -> EResult:
        """
        Connects to a server.

        Args:
            host: Optional server host to connect to. If None, a server will be selected from the list.
            port: Optional server port to connect to. If None, a server will be selected from the list.
            retry: If True, retries connecting if the initial connection attempt fails.

        Returns:
            EResult.OK if connection is successful, EResult.ConnectFailed otherwise.
        """
        while True:
            server = (
                (host, port)
                if host is not None and port is not None
                else await self._select_server()
            )

            if not server:
                return EResult.ConnectFailed

            host, port = server

            try:
                self.reader, self.writer = await asyncio.open_connection(host, port)
            except (OSError, ValueError, TimeoutError) as e:
                self._log.error(
                    "Failed to connect to server %s:%d: %s", host, port, e)

                if not retry:
                    return EResult.ConnectFailed

                continue

            if await self.perform_handshake():
                self.connected = True
                self._loop_task = asyncio.create_task(self._read_loop())
                return EResult.OK

            await self.disconnect()

            if not retry:
                return EResult.ConnectFailed

            self._log.info("Retrying connection...")

    async def perform_handshake(self) -> bool:
        """
        Performs the handshake with the server.

        Returns:
            True if the handshake was successful, False otherwise.
        """
        if self.writer is None:
            return False

        message = await self.listen()

        if message is None:
            self._log.error("No response received after connecting")
            return False

        packet = SteamPacket.parse(message)
        self._log.info("Received: %s", packet.emsg)

        if packet.emsg != EMsg.ChannelEncryptRequest or packet.body is None:
            self._log.error("Did not receive ChannelEncryptRequest")
            return False

        request = MsgChannelEncryptRequest(packet.body)
        session_key, encrypted_key = generate_session_key(request.challenge)
        crc = binascii.crc32(encrypted_key) & 0xFFFFFFFF

        response = MsgChannelEncryptResponse()
        response.key_size = len(encrypted_key)
        response.key = encrypted_key
        response.crc = crc

        header = MsgHdr()
        header.emsg = EMsg.ChannelEncryptResponse
        payload = header.pack() + response.pack()

        await self.send(payload)
        message = await self.listen()

        if message is None:
            self._log.error(
                "No response received after sending ChannelEncryptResponse")
            return False

        packet = SteamPacket.parse(message)

        if packet.emsg != EMsg.ChannelEncryptResult:
            self._log.error(
                "Did not receive ChannelEncryptResult after sending response"
            )
            return False

        self.session_key = session_key
        self.hmac_secret = session_key[:16]
        return True

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
                    self._log.error("Error parsing packet: %s", e)
            else:
                if self.connected:
                    self._log.warning("Connection lost in read loop")
                    await self.disconnect()

                break

    async def _select_server(self) -> tuple[str, int] | None:
        if not self.server_list:
            await self.get_server_list()

        for host, port in self.server_list:
            latency = await self._test_server_latency(host, port)
            if latency is not None and latency < 5:
                return (host, port)

        return None

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

    def next_job_id(self) -> int:
        """
        Generates the next job ID.

        Returns:
            The next job ID as an integer.
        """
        return next(self._global_job_id)

    async def send_protobuf_message(
        self,
        emsg: EMsg,
        message: Message,
        steam_id: int | None = None,
        job_id: int | None = None,
    ) -> int | None:
        """
        Sends a protobuf message to the server.

        Args:
            emsg: The EMsg identifier for the message.
            message: The protobuf message to send.
            steam_id: Optional Steam ID to include in the message header.
        """
        if not self.connected:
            self._log.error("The client is not connected")
            return None

        job_id = job_id or self.next_job_id()
        header = CMsgProtoBufHeader()
        header.jobid_source = job_id
        header.steamid = steam_id if steam_id is not None else self.steam_id
        header.client_sessionid = self._session_id

        header_data = header.SerializeToString()
        body_data = message.SerializeToString()

        emsg_id = ProtobufManager.add_mask(emsg)
        data = struct.pack("<I", emsg_id)
        data += struct.pack("<I", len(header_data))
        data += header_data
        data += body_data

        await self.send(data)
        return job_id

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
            self.writer.write(
                len(data).to_bytes(4, byteorder="little") +
                MAGIC_HEADER.encode() + data
            )
            await self.writer.drain()
            return True

        except Exception as e:
            self._log.error("Error sending data: %s", e)
            return False

    async def listen(self) -> bytes | None:
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
                        message, self.session_key, self.hmac_secret
                    )
                else:
                    message = symmetric_decrypt(message, self.session_key)

            return message

        except asyncio.IncompleteReadError:
            self._log.warning("Server closed connection")
            return None
        except Exception as e:
            self._log.error("Error listening: %s", e)
            return None
