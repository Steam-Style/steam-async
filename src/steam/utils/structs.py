import struct


class StructBase:
    def pack(self) -> bytes:
        """
        Packs the struct into bytes.

        Returns:
            The packed bytes.
        """
        raise NotImplementedError


class MsgHdr(StructBase):
    """
    Standard 20-byte Header for non-protobuf messages.
    """

    FMT = "<IQQ"
    SIZE = struct.calcsize(FMT)

    def __init__(self, data: bytes | None = None):
        """
        Initializes the MsgHdr.

        Args:
            data: Optional bytes to unpack.
        """
        if data:
            self.emsg, self.target_job_id, self.source_job_id = struct.unpack(
                self.FMT, data
            )
        else:
            self.emsg = 0
            self.target_job_id = 0xFFFFFFFFFFFFFFFF
            self.source_job_id = 0xFFFFFFFFFFFFFFFF

    def pack(self) -> bytes:
        """
        Packs the MsgHdr into bytes.

        Returns:
            The packed bytes.
        """
        return struct.pack(self.FMT, self.emsg, self.target_job_id, self.source_job_id)


class MsgChannelEncryptRequest(StructBase):
    """
    Received from Steam to start handshake.
    """

    FMT = "<II"

    def __init__(self, data: bytes):
        """
        Initializes the MsgChannelEncryptRequest.

        Args:
            data: The bytes to unpack.
        """
        struct_data = struct.unpack_from(self.FMT, data)
        self.protocol_version: int = struct_data[0]
        self.universe: int = struct_data[1]
        self.challenge: bytes = data[struct.calcsize(self.FMT) :]


class MsgChannelEncryptResponse(StructBase):
    """
    Sent to Steam to negotiate encryption.
    """

    FMT = "<II"

    def __init__(self):
        """
        Initializes the MsgChannelEncryptResponse.
        """
        self.protocol_version = 1
        self.key_size = 128
        self.key = b""
        self.crc = 0

    def pack(self) -> bytes:
        """
        Packs the MsgChannelEncryptResponse into bytes.

        Returns:
            The packed bytes.
        """
        return (
            struct.pack(self.FMT, self.protocol_version, self.key_size)
            + self.key
            + struct.pack("<I", self.crc)
        )
