from typing import Protocol, Any


class CMClientProtocol(Protocol):
    def send_protobuf_message(
        self, emsg: Any, message: Any, steam_id: Any = None
    ) -> Any: ...

    def wait_for(
        self, event: Any, timeout: Any = None, check: Any = None
    ) -> Any: ...
