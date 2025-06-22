import logging

import adafruit_ds3231


class RTC:
    def __init__(self, i2c) -> None:
        self.rtc = adafruit_ds3231.DS3231(i2c)

    def set_rtc_time(self, time_data) -> None:
        try:
            self.rtc.datetime = time_data.timetuple()
        except Exception as e:
            logging.error(f"Failed to set RTC time: {e}")

    def get_rtc_time(self):
        try:
            rtc_time = self.rtc.datetime
            return rtc_time.tm_hour, rtc_time.tm_min, rtc_time.tm_sec
        except Exception as e:
            logging.error(f"Failed to get RTC time: {e}")
            return None
