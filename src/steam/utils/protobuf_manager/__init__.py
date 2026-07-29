import fnmatch
import importlib
import os
import pkgutil
import sys

from google.protobuf.message import Message

from steam.enums.emsg import EMsg

PROTOBUF_MASK = 0x80000000

protobuf_overrides = {
    EMsg.ClientToGC: "cmsggcclient",
    EMsg.ClientFromGC: "cmsggcclient",
    EMsg.ClientGetNumberOfCurrentPlayersDP: "cmsgdpgetnumberofcurrentplayers",
    EMsg.ClientGetNumberOfCurrentPlayersDPResponse: "cmsgdpgetnumberofcurrentplayersresponse",
    EMsg.ClientLogonGameServer: "cmsgclientlogon",
    EMsg.ClientCurrentUIMode: "cmsgclientuimode",
    EMsg.ClientChatOfflineMessageNotification: "cmsgclientofflinemessagenotification",
}

cmsg_lookup: dict[str, type[Message]] = {}
protobufs_path = os.path.join(os.path.dirname(__file__), "protobufs")

if protobufs_path not in sys.path:
    sys.path.append(protobufs_path)

for module_info in pkgutil.iter_modules([protobufs_path]):
    if not module_info.name.endswith("_pb2"):
        continue

    try:
        module = importlib.import_module(
            f".protobufs.{module_info.name}", package=__name__
        )
    except ImportError:
        continue

    cmsg_list = fnmatch.filter(module.__dict__, "CMsg*")

    for cmsg_name in cmsg_list:
        cmsg_lookup[cmsg_name.lower()] = getattr(module, cmsg_name)


class ProtobufManager:
    """
    Manages Steam Protobuf messages.
    """

    @staticmethod
    def get_protobuf(emsg: EMsg) -> type[Message] | None:
        """
        Returns the protobuf corresponding to the given EMsg.
        """
        if emsg in protobuf_overrides:
            return cmsg_lookup.get(protobuf_overrides[emsg])

        lookup_key = f"cmsg{emsg.name.lower()}"
        proto = cmsg_lookup.get(lookup_key)

        if proto:
            return proto

        if "_Deprecated" in emsg.name:
            lookup_key = f"cmsg{emsg.name.replace('_Deprecated', '').lower()}"
            return cmsg_lookup.get(lookup_key)

        return None

    @staticmethod
    def is_protobuf(emsg_id: int) -> bool:
        """
        Checks if the given emsg_id has the protobuf mask set.

        Args:
            emsg_id: The integer emsg_id to check.

        Returns:
            True if the protobuf mask is set, False otherwise.
        """
        return (int(emsg_id) & PROTOBUF_MASK) > 0

    @staticmethod
    def add_mask(emsg_id: int) -> int:
        """
        Sets the protobuf mask on the given emsg_id.

        Args:
            emsg_id: The original integer emsg_id.

        Returns:
            The integer emsg_id with the protobuf mask applied.
        """
        return emsg_id | PROTOBUF_MASK

    @staticmethod
    def remove_mask(emsg_id: int) -> int:
        """
        Clears the protobuf mask from the given emsg_id.

        Args:
            emsg_id: The integer emsg_id with the protobuf mask.

        Returns:
            The integer emsg_id without the protobuf mask.
        """
        return emsg_id & ~PROTOBUF_MASK
