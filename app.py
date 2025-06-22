import logging
import signal
import sys
import threading
import time
from datetime import datetime

import adafruit_ds3231
import adafruit_fram
import board
import RPi.GPIO as GPIO
from flask import Flask

from functions.clock import CLOCK
from functions.fram import FRAM
from functions.ntp import NTP
from functions.rtc import RTC

# Replace these with ENVs?
hour_hand_position: int = 0
minute_hand_position: int = 0
second_hand_position: int = 0
tick_pin1: int = 0
tick_pin2: int = 0
ntp_server: str = "time.nist.gov"
ntp_port: int = 123
ntp_sync_interval: int = 300

# Global variables
lock = threading.Lock()  # Create a lock for thread safety

# Setup
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(tick_pin1, GPIO.OUT)
GPIO.setup(tick_pin2, GPIO.OUT)
GPIO.output(tick_pin1, GPIO.LOW)
GPIO.output(tick_pin2, GPIO.LOW)

# Initialize I2C and RTC
i2c = board.I2C()
rtc = adafruit_ds3231.DS3231(i2c)
fram = adafruit_fram.FRAM_I2C(i2c)

# Initialize Flask app
app = Flask(__name__, static_url_path="/static")

# Disable Flask's default logging
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

# Initialize logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

clock: CLOCK = CLOCK(
    hour_hand_position, minute_hand_position, second_hand_position, tick_pin1, tick_pin2
)

ntp: NTP = NTP(ntp_server, ntp_port, ntp_sync_interval)

rtc: RTC = RTC(i2c)

fram: FRAM = FRAM(i2c)


def sync_rtc_time_with_ntp_time(ntp: NTP, rtc: RTC) -> None:
    try:
        ntp_time: datetime | None = ntp.get_ntp_time()
        if ntp_time:
            rtc.set_rtc_time(ntp_time)
    except Exception as e:
        logging.error(f"Failed to sync RTC time with NTP time: {e}")


def continuous_sync_rtc_time_with_ntp_time(
    ntp_sync_interval: int, ntp: NTP, rtc: RTC
) -> None:
    while True:
        sync_rtc_time_with_ntp_time(ntp, rtc)
        time.sleep(ntp_sync_interval)


def timer_callback(tick_event):
    while True:
        time.sleep(0.25 if fast_forward else 1)
        with lock:
            if not paused:  # Check if the clock is paused
                tick_event.set()


def signal_handler(signum, frame):
    logging.info("Signal received, cleaning up GPIO and exiting...")
    GPIO.cleanup()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    tick_event = threading.Event()

    time_string = read_time_from_fram()
    if time_string:
        hour, minute, second = map(int, time_string.split(":"))
        CLOCK_HOUR_HAND_POSITION = hour % 12 or 12
        CLOCK_MINUTE_HAND_POSITION = minute
        CLOCK_SECOND_HAND_POSITION = second

    sync_rtc_time_with_ntp_time(on_startup=True)

    timer_thread = threading.Thread(target=timer_callback, args=(tick_event,))
    timer_thread.daemon = True
    timer_thread.start()

    sync_timer_thread = threading.Thread(target=continuous_sync_rtc_time_with_ntp_time)
    sync_timer_thread.daemon = True
    sync_timer_thread.start()

    flask_thread = threading.Thread(
        target=app.run, kwargs={"host": "0.0.0.0", "port": 5000}
    )
    flask_thread.daemon = True
    flask_thread.start()

    try:
        while True:
            tick_event.wait()
            with lock:
                tick_event.clear()
                synchronize_clock()
                write_time_to_fram()
    except (KeyboardInterrupt, SystemExit):
        signal_handler(None, None)


if __name__ == "__main__":
    main()
