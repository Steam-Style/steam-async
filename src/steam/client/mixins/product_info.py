import logging
import asyncio
from typing import Optional, Any, TYPE_CHECKING
from steam.enums.emsg import EMsg
from steam.client.mixins.protocols import CMClientProtocol
from steam.utils.vdf import VDFParser
from steam.utils.protobuf_manager.protobufs.steammessages_clientserver_appinfo_pb2 import (
    CMsgClientPICSProductInfoRequest,
    CMsgClientPICSAccessTokenRequest,
    CMsgClientPICSAccessTokenResponse,
    CMsgClientPICSProductInfoResponse
)

if TYPE_CHECKING:
    _Base = CMClientProtocol
else:
    _Base = object


class ProductInfoMixin(_Base):
    """
    Mixin providing product info functionality for the Steam client.
    """

    _log: logging.Logger = logging.getLogger(__name__)

    async def get_product_info(self, app_ids: list[int], access_tokens: Optional[dict[int, int]] = None, timeout: int = 20) -> Optional[dict[int, dict[str, Any]]]:
        """
        Requests product info for the specified app IDs.

        Args:
            app_ids: List of application IDs to request info for.
            access_tokens: Optional dictionary of access tokens for the apps.
            timeout: Timeout in seconds for the request.

        Returns:
            A dictionary mapping app IDs to their parsed product info, or None if the request times out.
        """
        access_tokens = access_tokens if access_tokens is not None else {}
        request = CMsgClientPICSProductInfoRequest()

        for app_id in app_ids:
            app = request.apps.add()
            app.appid = app_id

            if app_id in access_tokens:
                app.access_token = access_tokens[app_id]

        await self.send_protobuf_message(EMsg.ClientPICSProductInfoRequest, request)

        try:
            packet = await self.wait_for(EMsg.ClientPICSProductInfoResponse, timeout=timeout)
            body = packet.body

            if isinstance(body, bytes):
                response = CMsgClientPICSProductInfoResponse()
                response.ParseFromString(body)
            else:
                response = body
            return self._parse_product_info(response)

        except asyncio.TimeoutError:
            return None

    def _parse_product_info(self, response: Any) -> dict[int, dict[str, Any]]:
        parsed_apps: dict[int, dict[str, Any]] = {}

        for app in response.apps:
            vdf_data = app.buffer.decode(
                "utf-8", errors="replace").rstrip("\x00")
            parsed_vdf = VDFParser().parse(vdf_data)
            parsed_apps[app.appid] = parsed_vdf

        return parsed_apps

    async def get_access_tokens(self, app_ids: list[int], timeout: int = 20) -> dict[int, int]:
        """
        Requests access tokens for the specified app IDs.

        Args:
            app_ids: List of application IDs to request access tokens for.
            timeout: Timeout in seconds for the request.

        Returns:
            A dictionary mapping app IDs to their access tokens.
        """
        request = CMsgClientPICSAccessTokenRequest()
        request.appids.extend(app_ids)

        await self.send_protobuf_message(EMsg.ClientPICSAccessTokenRequest, request)

        try:
            packet = await self.wait_for(EMsg.ClientPICSAccessTokenResponse, timeout=timeout)

            response: Any = packet.body
            if isinstance(response, bytes):
                response = CMsgClientPICSAccessTokenResponse()
                response.ParseFromString(packet.body)

            tokens: dict[int, int] = {}
            for app_token in response.app_access_tokens:
                tokens[app_token.appid] = app_token.access_token

            return tokens

        except asyncio.TimeoutError:
            return {}
