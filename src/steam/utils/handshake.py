import binascii
import logging
from typing import TYPE_CHECKING
from steam.enums.emsg import EMsg
from steam.utils.packet import SteamPacket
from steam.utils.crypto import generate_session_key
from steam.utils.structs import (
    MsgChannelEncryptRequest,
    MsgChannelEncryptResponse,
    MsgHdr,
)

if TYPE_CHECKING:
    from steam.utils.cm_client import CMClient

LOG = logging.getLogger(__name__)


async def perform_handshake(client: "CMClient") -> bool:
    """
    Performs the handshake with the Connection Manager server.

    Args:
        client: The CMClient instance.

    Returns:
        True if the handshake was successful, False otherwise.
    """
    if client.writer is None:
        return False

    message = await client.listen()

    if message is None:
        LOG.error("No response received after connecting")
        return False

    packet = SteamPacket.parse(message)
    LOG.info("Received: %s", packet.emsg)

    if packet.emsg != EMsg.ChannelEncryptRequest or packet.body is None:
        LOG.error("Did not receive ChannelEncryptRequest")
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

    await client.send(payload)
    message = await client.listen()

    if message is None:
        LOG.error("No response received after sending ChannelEncryptResponse")
        return False

    packet = SteamPacket.parse(message)

    if packet.emsg != EMsg.ChannelEncryptResult:
        LOG.error("Did not receive ChannelEncryptResult after sending response")
        return False

    client.session_key = session_key
    client.hmac_secret = session_key[:16]
    return True
