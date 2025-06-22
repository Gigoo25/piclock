import logging

import adafruit_fram


class FRAM:
    def __init__(self, i2c) -> None:
        self.fram = adafruit_fram.FRAM_I2C(i2c)

    def write_time_to_fram(
        self,
        hour_hand_position: int,
        minute_hand_position: int,
        second_hand_position: int,
    ) -> None:
        try:
            time_string = f"{hour_hand_position:02}:{minute_hand_position:02}:{second_hand_position:02}"
            self.fram[0:8] = bytearray(time_string.encode("utf-8"))
            logging.info(f"Wrote clock time '{time_string}' to FRAM.")
        except Exception as e:
            logging.error(f"Failed to write time to FRAM: {e}")

    def read_time_from_fram(self) -> str | None:
        try:
            time_bytes = self.fram[0:8]
            time_string = time_bytes.decode("utf-8")
            logging.info(f"Read time from FRAM at address 0: {time_string}")
            return time_string
        except Exception as e:
            logging.error(f"Failed to read time from FRAM: {e}")
            return None
