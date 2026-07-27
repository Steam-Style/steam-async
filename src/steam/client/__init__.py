import logging
import os
from steam.utils.cm_client import CMClient
from steam.client.mixins import LogonMixin, AppsMixin


class SteamClient(CMClient, LogonMixin, AppsMixin):
    """
    A client for interacting with the Steam network.
    """

    _log: logging.Logger = logging.getLogger(__name__)

    def __init__(self):
        """
        Initializes the SteamClient.
        """
        super().__init__()
        self.logged_in: bool = False
        self.machine_id: bytes = os.urandom(16)
