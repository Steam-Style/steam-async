import logging
import asyncio
from typing import Optional, Any, TYPE_CHECKING
from steam.enums.emsg import EMsg
from steam.enums.common import EResult
from steam.client.mixins.protocols import CMClientProtocol
from steam.utils.protobuf_manager import ProtobufManager
from steam.utils.packet import SteamPacket
from steam.utils.protobuf_manager.protobufs.steammessages_base_pb2 import (
    CMsgProtoBufHeader,
)
from steam.utils.protobuf_manager.protobufs.steammessages_clientserver_login_pb2 import (
    CMsgClientHeartBeat,
)

if TYPE_CHECKING:
    _Base = CMClientProtocol
else:
    _Base = object


class LogonMixin(_Base):
    """
    Mixin providing logon functionality for the Steam client.
    """

    _log: logging.Logger = logging.getLogger(__name__)
    _heartbeat_task: Optional[asyncio.Task[None]] = None

    connected: bool
    machine_id: bytes
    logged_in: bool
    steam_id: int

    async def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_code: Optional[str] = None,
        two_factor_code: Optional[str] = None,
    ) -> EResult:
        """
        Logs in the client with the provided credentials or anonymously if none are
            provided

        Args:
            username: The username for login.
            password: The password for login.
            auth_code: The Steam Guard email code.
            two_factor_code: The Steam Guard mobile 2FA code.

        Returns:
            An EResult indicating the outcome of the login attempt.
        """
        if username is None and password is None:
            return await self.anonymous_login()

        if not self.connected:
            self._log.error("The client is not connected")
            return EResult.NoConnection

        proto_class = ProtobufManager.get_protobuf(EMsg.ClientLogon)

        if proto_class is None:
            self._log.error("Failed to get ClientLogon protobuf")
            return EResult.Fail

        message: Any = proto_class()
        message.protocol_version = 65580
        message.client_package_version = 1561159470
        message.client_os_type = 16
        message.client_language = "english"
        message.machine_id = self.machine_id
        message.account_name = username
        message.password = password

        if auth_code:
            message.auth_code = auth_code

        if two_factor_code:
            message.two_factor_code = two_factor_code

        steam_id = 76561197960265728

        response_future = self.create_listener(EMsg.ClientLogOnResponse)
        await self.send_protobuf_message(EMsg.ClientLogon, message, steam_id=steam_id)

        return self._handle_logon_response(await response_future)

    async def anonymous_login(self) -> EResult:
        """
        Logs in the client without credentials.

        Returns:
            An EResult indicating the outcome of the login attempt.
        """
        if not self.connected:
            self._log.error("The client is not connected")
            return EResult.NoConnection

        proto_class = ProtobufManager.get_protobuf(EMsg.ClientLogon)

        if proto_class is None:
            self._log.error("Failed to get ClientLogon protobuf")
            return EResult.Fail

        message: Any = proto_class()
        message.protocol_version = 65575
        message.client_package_version = 1561159470
        message.client_os_type = 16
        message.client_language = "english"
        message.machine_id = self.machine_id

        steam_id = 117093590311632896

        response_future = self.create_listener(EMsg.ClientLogOnResponse)
        await self.send_protobuf_message(EMsg.ClientLogon, message, steam_id=steam_id)

        return self._handle_logon_response(await response_future)

    async def logout(self) -> EResult:
        """
        Logs out the client.

        Returns:
            An EResult indicating the outcome of the logout attempt.
        """
        if not self.logged_in:
            self._log.error("The client is not logged in")
            return EResult.InvalidState

        proto_class = ProtobufManager.get_protobuf(EMsg.ClientLogOff)

        if proto_class is None:
            self._log.error("Failed to get ClientLogOff protobuf")
            return EResult.Fail

        message: Any = proto_class()
        await self.send_protobuf_message(EMsg.ClientLogOff, message)

        self.logged_in = False
        self._stop_heartbeat()
        return EResult.OK

    def _handle_logon_response(self, packet: SteamPacket) -> EResult:
        if (
            packet.body
            and not isinstance(packet.body, (bytes, bytearray, memoryview))
            and hasattr(packet.body, "eresult")
        ):
            result = EResult(packet.body.eresult)
            self._log.info("Login result: %s", result)

            if result == EResult.OK:
                self.logged_in = True
                if packet.header and isinstance(packet.header, CMsgProtoBufHeader):
                    self.steam_id = packet.header.steamid
                    self._log.info("Logged in with SteamID: %s", self.steam_id)

                self._start_heartbeat()

            return result

        return EResult.Fail

    def _start_heartbeat(self):
        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._log.debug("Heartbeat task started")

    def _stop_heartbeat(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
            self._log.debug("Heartbeat task stopped")

    async def _heartbeat_loop(self):
        interval = 30

        while self.connected and self.logged_in:
            try:
                heartbeat: Any = CMsgClientHeartBeat()
                await self.send_protobuf_message(EMsg.ClientHeartBeat, heartbeat)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error("Error in heartbeat loop: %s", e)
                await asyncio.sleep(interval)

        return None
