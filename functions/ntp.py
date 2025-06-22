import logging
from datetime import datetime

import ntplib


class NTP:
    def __init__(
        self,
        ntp_server: str,
        ntp_port: int,
        ntp_sync_interval: int,
    ) -> None:
        self.ntp_server: str = ntp_server
        self.ntp_port: int = ntp_port
        self.ntp_sync_interval: int = ntp_sync_interval

    def get_ntp_time(self) -> datetime | None:
        try:
            ntp_client = ntplib.NTPClient()
            ntp_response = ntp_client.request(
                self.ntp_server, version=3, port=self.ntp_port
            )
            return datetime.fromtimestamp(ntp_response.tx_time)
        except Exception as e:
            logging.error(f"Failed to get NTP time: {e}")
            return None
