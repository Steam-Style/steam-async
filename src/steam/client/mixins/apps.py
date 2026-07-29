import asyncio
import logging
from typing import TYPE_CHECKING, Any, Literal

import vdf

from steam.client.mixins.protocols import CMClientProtocol
from steam.enums.emsg import EMsg
from steam.utils.protobuf_manager.protobufs.steammessages_clientserver_appinfo_pb2 import (
    CMsgClientPICSAccessTokenRequest,
    CMsgClientPICSAccessTokenResponse,
    CMsgClientPICSProductInfoRequest,
    CMsgClientPICSProductInfoResponse,
)

if TYPE_CHECKING:
    _Base = CMClientProtocol
else:
    _Base = object


class AppsMixin(_Base):
    """
    Mixin providing product info functionality for the Steam client.
    """

    _log: logging.Logger = logging.getLogger(__name__)

    async def get_product_info(
        self,
        app_ids: list[int] | None = None,
        package_ids: list[int] | None = None,
        meta_data_only: bool | None = False,
        access_tokens: dict[int, int] | None = None,
        timeout: int = 20,
    ) -> dict[Literal["apps", "packages"], dict[int, dict[str, Any]]] | None:
        """
        Requests product info for the specified app IDs.

        Args:
            app_ids: List of application IDs to request info for.
            package_ids: List of package IDs to request info for.
            access_tokens: Optional dictionary of access tokens for the apps and packages.
            timeout: Timeout in seconds for the request.

        Returns:
            A dictionary mapping app IDs to their parsed product info, or None if the request times out.
        """
        if app_ids is None and package_ids is None:
            return None

        request = CMsgClientPICSProductInfoRequest()
        request.meta_data_only = meta_data_only or False
        request.num_prev_failed = 0

        app_ids = app_ids or []
        package_ids = package_ids or []
        access_tokens = access_tokens or {}

        for app_id in app_ids:
            app = request.apps.add()
            app.appid = app_id

            if app_id in access_tokens:
                app.access_token = access_tokens[app_id]

        for package_id in package_ids:
            package = request.packages.add()
            package.packageid = package_id

            if package_id in access_tokens:
                package.access_token = access_tokens[package_id]

        parsed_response: dict[
            Literal["apps", "packages"], dict[int, dict[str, Any]]
        ] = {
            "apps": {},
            "packages": {},
        }
        job_id = self.next_job_id()
        stream = self.create_stream_listener(
            EMsg.ClientPICSProductInfoResponse,
            check=lambda pkt: pkt.header.jobid_target == job_id,
        )
        await self.send_protobuf_message(
            EMsg.ClientPICSProductInfoRequest, request, job_id=job_id
        )

        try:
            while True:
                try:
                    packet = await asyncio.wait_for(stream.queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    return None

                body = packet.body

                if isinstance(body, bytes):
                    response = CMsgClientPICSProductInfoResponse()
                    response.ParseFromString(body)
                else:
                    response = body

                for app in response.apps:
                    parsed_vdf = vdf.loads(app.buffer[:-1].decode("utf-8", "replace"))[
                        "appinfo"
                    ]
                    parsed_response["apps"][app.appid] = parsed_vdf

                for package in response.packages:
                    parsed_vdf = vdf.binary_loads(package.buffer[4:]).get(
                        str(package.packageid), {}
                    )
                    parsed_response["packages"][package.packageid] = parsed_vdf

                if not response.response_pending:
                    break
        finally:
            stream.close()

        return parsed_response

    async def get_access_tokens(
        self, app_ids: list[int], timeout: int = 20
    ) -> dict[int, int]:
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

        response_future = self.create_stream_listener(
            EMsg.ClientPICSAccessTokenResponse,
            check=lambda packet: packet.header.jobid_target == self.next_job_id(),
        )
        await self.send_protobuf_message(EMsg.ClientPICSAccessTokenRequest, request)

        try:
            packet = await response_future
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
