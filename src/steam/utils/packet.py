import struct
import io
from typing import Union, Any
import gzip
import zipfile
from steam.enums.emsg import EMsg
from steam.utils.structs import MsgHdr
from steam.utils.protobuf_manager import ProtobufManager
from steam.utils.protobuf_manager.protobufs.steammessages_base_pb2 import (
    CMsgProtoBufHeader,
    CMsgMulti,
)


class SteamPacket:
    """
    Represents a Steam network packet, either Protobuf or non-Protobuf.
    """

    def __init__(self, emsg: Union[EMsg, int], data: bytes, is_protobuf: bool):
        """
        Initializes a SteamPacket instance.

        Args:
            emsg: The EMsg identifier.
            data: The raw packet data.
            is_protobuf: Whether the packet is a Protobuf packet.
        """
        self.emsg: Union[EMsg, int] = emsg
        self.is_protobuf: bool = is_protobuf
        self.header: Union[MsgHdr, CMsgProtoBufHeader, None] = None
        self.body: Union[bytes, Any, None] = None

        if self.is_protobuf and isinstance(emsg, EMsg):
            stream = io.BytesIO(data)
            header_len = struct.unpack("<I", stream.read(4))[0]
            header_data = stream.read(header_len)

            self.header = CMsgProtoBufHeader()
            self.header.ParseFromString(header_data)

            proto_class = ProtobufManager.get_protobuf(emsg)

            if proto_class:
                self.body = proto_class()
                self.body.ParseFromString(stream.read())
            else:
                self.body = stream.read()
        else:
            header_data = struct.pack("<I", int(emsg)) + data[:16]
            self.header = MsgHdr(header_data)
            self.body = data[16:]

    @classmethod
    def parse(cls, data: bytes) -> "SteamPacket":
        """
        Parses raw data into a SteamPacket instance.

        Args:
            data: The raw bytes of the packet.

        Returns:
            A SteamPacket instance.
        """
        emsg_id = struct.unpack_from("<I", data)[0]
        is_protobuf = False

        if ProtobufManager.is_protobuf(emsg_id):
            is_protobuf = True
            emsg_id = ProtobufManager.remove_mask(emsg_id)

        try:
            emsg = EMsg(emsg_id)
        except ValueError:
            emsg = emsg_id

        return cls(emsg, data[4:], is_protobuf)

    def unpack_multi(self) -> list["SteamPacket"]:
        """
        Unpacks a Multi packet into a list of SteamPackets.

        Returns:
            A list of SteamPacket instances contained within the Multi packet.
        """
        if self.emsg != EMsg.Multi:
            return []

        multi: Any = CMsgMulti()

        if isinstance(self.body, bytes):
            multi.ParseFromString(self.body)
        elif self.body:
            multi = self.body
        else:
            return []

        if multi.size_unzipped:
            if multi.message_body.startswith(b"PK"):
                with zipfile.ZipFile(io.BytesIO(multi.message_body)) as zf:
                    data = zf.read(zf.namelist()[0])
            else:
                data = gzip.decompress(multi.message_body)
        else:
            data = multi.message_body

        packets: list["SteamPacket"] = []
        offset = 0

        while offset < len(data):
            msg_len = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            msg_data = data[offset : offset + msg_len]
            offset += msg_len
            packets.append(SteamPacket.parse(msg_data))

        return packets
