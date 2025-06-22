import logging
import signal
import sys
import time

import adafruit_ds3231
import adafruit_fram
import board
import RPi.GPIO as GPIO
from flask import Flask

from functions.clock import Clock
from functions.fram import FRAM
from functions.ntp import NTP
from functions.rtc import RTC
from functions.thread_manager import ThreadManager
from functions.web import WebUI

# Configuration
tick_pin1 = 12
tick_pin2 = 13
ntp_server = "time.nist.gov"
ntp_port = 123
ntp_sync_interval = 300

# Initialize logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Setup GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(tick_pin1, GPIO.OUT)
GPIO.setup(tick_pin2, GPIO.OUT)
GPIO.output(tick_pin1, GPIO.LOW)
GPIO.output(tick_pin2, GPIO.LOW)

# Initialize I2C and hardware components
i2c = board.I2C()
rtc = adafruit_ds3231.DS3231(i2c)
fram = adafruit_fram.FRAM_I2C(i2c)

# Initialize Flask app
app = Flask(__name__, static_url_path="/static")
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

# Initialize services
ntp = NTP(ntp_server, ntp_port, ntp_sync_interval)
rtc_service = RTC(i2c)
fram_service = FRAM(i2c)


# Thread functions with consistent signature (including stop_event)
def timer_function(clock, tick_event, stop_event):
    """Timer thread that triggers clock ticks"""
    while not stop_event.is_set():
        # Calculate sleep time based on clock mode
        sleep_time = 0.25 if clock.fast_forward else 1.0

        # Use wait with timeout to allow for clean shutdown
        if stop_event.wait(timeout=sleep_time):
            break

        # Set the tick event if clock is not paused
        if not clock.paused:
            tick_event.set()


def syncing_function(ntp_sync_interval, ntp, rtc_service, stop_event):
    """Thread that periodically syncs RTC with NTP time"""
    while not stop_event.is_set():
        try:
            ntp_time = ntp.get_ntp_time()
            if ntp_time:
                rtc_service.set_rtc_time(ntp_time)
                logging.info(f"Synced RTC with NTP time: {ntp_time}")
        except Exception as e:
            logging.error(f"Failed to sync RTC time with NTP time: {e}")

        # Sleep with periodic checks for stop event
        for _ in range(int(ntp_sync_interval / 5)):
            if stop_event.is_set():
                break
            time.sleep(5)


def web_server_function(app, host, port, stop_event):
    """Thread that runs the Flask web server"""
    # Configure Flask to respond to the stop event
    from threading import Thread

    stop_event_monitor = Thread(
        target=lambda: (stop_event.wait(), logging.info("Shutting down Flask server"))
    )
    stop_event_monitor.daemon = True
    stop_event_monitor.start()

    # Run Flask with threaded=True to allow for shutdown
    app.run(host=host, port=port, threaded=True)


def cleanup():
    """Clean up resources before exiting"""
    logging.info("Cleaning up resources...")
    GPIO.cleanup()


def signal_handler(signum, frame, thread_manager=None):
    """Handle termination signals"""
    logging.info(f"Received signal {signum}, shutting down...")
    if thread_manager:
        thread_manager.stop_all()
    cleanup()
    sys.exit(0)


def main():
    # Initialize thread manager
    thread_manager = ThreadManager()

    # Update signal handlers to use thread manager
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, thread_manager))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, thread_manager))

    # Get the time from FRAM
    time_string = fram_service.read_time_from_fram()
    if time_string:
        logging.info(f"Time read from FRAM: {time_string}")
        fram_hour, fram_minute, fram_second = map(int, time_string.split(":"))
        fram_hour = fram_hour % 12 or 12
    else:
        logging.info("No time found in FRAM, setting to default")
        fram_hour, fram_minute, fram_second = 12, 0, 0

    # Sync RTC with NTP time at startup
    try:
        ntp_time = ntp.get_ntp_time()
        if ntp_time:
            rtc_service.set_rtc_time(ntp_time)
            logging.info(f"Initial RTC sync with NTP time: {ntp_time}")
    except Exception as e:
        logging.error(f"Failed initial RTC sync: {e}")

    # Initialize the clock with the FRAM time
    clock = Clock(
        fram_hour,
        fram_minute,
        fram_second,
        tick_pin1,
        tick_pin2,
    )

    # Initialize web UI and web server
    WebUI(
        app,
        clock,
        ntp,
        rtc_service,
        fram_service,
        {"server": ntp_server, "port": ntp_port, "sync_interval": ntp_sync_interval},
    )

    # Register and start threads
    thread_manager.add_thread(
        target=timer_function, args=(clock, thread_manager.tick_event)
    )

    thread_manager.add_thread(
        target=syncing_function, args=(ntp_sync_interval, ntp, rtc_service)
    )

    # Now start the web server thread
    thread_manager.add_thread(target=web_server_function, args=(app, "0.0.0.0", 5000))

    thread_manager.start_all()

    # Main loop for clock synchronization
    try:
        while not thread_manager.is_stopping():
            # Wait for a tick event
            if thread_manager.tick_event.wait(timeout=1.0):
                with thread_manager.lock:
                    thread_manager.tick_event.clear()

                    # Get current time from RTC
                    rtc_time_data = rtc_service.get_rtc_time()
                    if rtc_time_data:
                        rtc_hour, rtc_minute, rtc_second = rtc_time_data

                        if (
                            rtc_hour is not None
                            and rtc_minute is not None
                            and rtc_second is not None
                        ):
                            # Synchronize clock with RTC time
                            clock_time_positions = clock.synchronize_clock(
                                rtc_hour, rtc_minute, rtc_second
                            )

                            if clock_time_positions:
                                # Unpack and save the current positions
                                hour_pos, minute_pos, second_pos = clock_time_positions

                                if (
                                    hour_pos is not None
                                    and minute_pos is not None
                                    and second_pos is not None
                                ):
                                    # Save current time to FRAM
                                    fram_service.write_time_to_fram(
                                        hour_pos, minute_pos, second_pos
                                    )

    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        # Ensure clean shutdown
        thread_manager.stop_all()
        cleanup()


if __name__ == "__main__":
    main()
