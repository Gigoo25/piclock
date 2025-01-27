import logging
import signal
import sys
import threading
import time
from datetime import datetime

import adafruit_ds3231
import adafruit_fram
import board
import ntplib
import RPi.GPIO as GPIO
from flask import Flask, redirect, render_template, request, url_for

# GPIO Constants
TICK_PIN1 = 12
TICK_PIN2 = 13

# NTP Constants
NTP_SYNC_INTERVAL = 300
NTP_SERVER = "time.nist.gov"

# Global variables
lock = threading.Lock()  # Create a lock for thread safety
current_tick_pin = TICK_PIN1  # Start with TICK_PIN1

# Clock status flags
fast_forward = False
paused = False
reverse = False

# Clock hand positions
CLOCK_HOUR_HAND_POSITION = None
CLOCK_MINUTE_HAND_POSITION = None
CLOCK_SECOND_HAND_POSITION = None

# Setup
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(TICK_PIN1, GPIO.OUT)
GPIO.setup(TICK_PIN2, GPIO.OUT)
GPIO.output(TICK_PIN1, GPIO.LOW)
GPIO.output(TICK_PIN2, GPIO.LOW)

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


def set_rtc_time(time_data):
    try:
        rtc.datetime = time_data.timetuple()
    except Exception as e:
        logging.error(f"Failed to set RTC time: {e}")


def get_rtc_time():
    try:
        rtc_time = rtc.datetime
        return rtc_time.tm_hour, rtc_time.tm_min, rtc_time.tm_sec
    except Exception as e:
        logging.error(f"Failed to get RTC time: {e}")
        return None


def write_time_to_fram():
    try:
        time_string = f"{CLOCK_HOUR_HAND_POSITION:02}:{CLOCK_MINUTE_HAND_POSITION:02}:{CLOCK_SECOND_HAND_POSITION:02}"
        fram[0:8] = bytearray(time_string.encode("utf-8"))
        logging.info(f"Wrote clock time '{time_string}' to FRAM.")
    except Exception as e:
        logging.error(f"Failed to write time to FRAM: {e}")


def read_time_from_fram():
    try:
        time_bytes = fram[0:8]
        time_string = time_bytes.decode("utf-8")
        logging.info(f"Read time from FRAM at address 0: {time_string}")
        return time_string
    except Exception as e:
        logging.error(f"Failed to read time from FRAM: {e}")
        return None


def sync_rtc_time_with_ntp_time(on_startup=False):
    try:
        ntp_time = get_ntp_time()
        if ntp_time:
            set_rtc_time(ntp_time)
            if on_startup:
                logging.info("RTC time synchronized with NTP time on startup")
    except Exception as e:
        logging.error(f"Failed to sync RTC time with NTP time: {e}")


def continuous_sync_rtc_time_with_ntp_time():
    while True:
        sync_rtc_time_with_ntp_time()
        time.sleep(NTP_SYNC_INTERVAL)


def get_ntp_time():
    try:
        ntp_client = ntplib.NTPClient()
        ntp_response = ntp_client.request(NTP_SERVER, version=3, port=123)
        return datetime.fromtimestamp(ntp_response.tx_time)
    except Exception as e:
        logging.error(f"Failed to get NTP time: {e}")
        return None


def send_pulse(pin, duration, next_tick_delay=0):
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(next_tick_delay)


def forward_tick():
    global current_tick_pin, reverse
    reverse = False
    send_pulse(current_tick_pin, 0.1)
    current_tick_pin = TICK_PIN2 if current_tick_pin == TICK_PIN1 else TICK_PIN1
    update_clock_position()


def reverse_tick():
    global current_tick_pin, reverse
    reverse = True
    send_pulse(current_tick_pin, 0.01)
    current_tick_pin = TICK_PIN1 if current_tick_pin == TICK_PIN2 else TICK_PIN2
    send_pulse(current_tick_pin, 0.03)
    update_clock_position(reverse=True)


def calculate_time_difference(ntp_hour, ntp_minute, ntp_second):
    if CLOCK_HOUR_HAND_POSITION == 12:
        clock_hour_24 = 0 if ntp_hour < 12 else 12
    else:
        clock_hour_24 = CLOCK_HOUR_HAND_POSITION
        if ntp_hour >= 12:
            clock_hour_24 += 12

    ntp_total_seconds = ntp_hour * 3600 + ntp_minute * 60 + ntp_second
    clock_total_seconds = (
        clock_hour_24 * 3600
        + CLOCK_MINUTE_HAND_POSITION * 60
        + CLOCK_SECOND_HAND_POSITION
    )

    total_seconds_diff = ntp_total_seconds - clock_total_seconds

    if total_seconds_diff > 21600:
        total_seconds_diff -= 43200
    elif total_seconds_diff < -21600:
        total_seconds_diff += 43200

    return total_seconds_diff


def update_clock_position(reverse=False):
    global \
        CLOCK_HOUR_HAND_POSITION, \
        CLOCK_MINUTE_HAND_POSITION, \
        CLOCK_SECOND_HAND_POSITION
    if reverse:
        CLOCK_SECOND_HAND_POSITION = (CLOCK_SECOND_HAND_POSITION - 1) % 60
        if CLOCK_SECOND_HAND_POSITION == 59:
            CLOCK_MINUTE_HAND_POSITION = (CLOCK_MINUTE_HAND_POSITION - 1) % 60
            if CLOCK_MINUTE_HAND_POSITION == 59:
                CLOCK_HOUR_HAND_POSITION = (CLOCK_HOUR_HAND_POSITION - 1) % 12
    else:
        CLOCK_SECOND_HAND_POSITION = (CLOCK_SECOND_HAND_POSITION + 1) % 60
        if CLOCK_SECOND_HAND_POSITION == 0:
            CLOCK_MINUTE_HAND_POSITION = (CLOCK_MINUTE_HAND_POSITION + 1) % 60
            if CLOCK_MINUTE_HAND_POSITION == 0:
                CLOCK_HOUR_HAND_POSITION = (CLOCK_HOUR_HAND_POSITION + 1) % 12


def synchronize_clock():
    hour, minute, second = get_rtc_time()
    total_seconds_diff = calculate_time_difference(hour, minute, second)

    logging.info(f"RTC time: {hour:02}:{minute:02}:{second:02}")
    logging.info(
        f"Clock time: {CLOCK_HOUR_HAND_POSITION:02}:{CLOCK_MINUTE_HAND_POSITION:02}:{CLOCK_SECOND_HAND_POSITION:02}"
    )

    if hour is not None:
        tolerance = 1

        if abs(total_seconds_diff) <= tolerance:
            logging.info("Clock is in sync with RTC time")
            set_fast_forward(False)
            forward_tick()
        elif total_seconds_diff > tolerance:
            logging.info(f"Clock is behind RTC time by {total_seconds_diff} seconds")
            set_fast_forward(True)
            forward_tick()
        else:
            logging.info(
                f"Clock is ahead of RTC time by {abs(total_seconds_diff)} seconds"
            )
            set_fast_forward(False)
            reverse_tick()


def set_fast_forward(value):
    global fast_forward
    fast_forward = value


def timer_callback(tick_event):
    while True:
        time.sleep(0.25 if fast_forward else 1)
        with lock:
            if not paused:  # Check if the clock is paused
                tick_event.set()


@app.route("/", methods=["GET", "POST"])
def index():
    global NTP_SERVER, NTP_SYNC_INTERVAL
    if request.method == "POST":
        if "set_time" in request.form:
            hour = int(request.form["hour"])
            minute = int(request.form["minute"])
            second = int(request.form["second"])
            global \
                CLOCK_HOUR_HAND_POSITION, \
                CLOCK_MINUTE_HAND_POSITION, \
                CLOCK_SECOND_HAND_POSITION
            CLOCK_HOUR_HAND_POSITION = hour
            CLOCK_MINUTE_HAND_POSITION = minute
            CLOCK_SECOND_HAND_POSITION = second
            initial_time = datetime.now().replace(
                hour=hour, minute=minute, second=second, microsecond=0
            )
            set_rtc_time(initial_time)
            return redirect(url_for("config"))
        elif "set_ntp" in request.form:
            ntp_server = request.form["ntp_server"]
            ntp_sync_interval = int(request.form["ntp_sync_interval"])
            NTP_SERVER = ntp_server
            NTP_SYNC_INTERVAL = ntp_sync_interval
            return redirect(url_for("config"))
    return render_template(
        "index.html", ntp_server=NTP_SERVER, ntp_sync_interval=NTP_SYNC_INTERVAL
    )


@app.route("/config", methods=["GET", "POST"])
def config():
    global NTP_SERVER, NTP_SYNC_INTERVAL
    if request.method == "POST":
        if "set_time" in request.form:
            hour = int(request.form["hour"])
            minute = int(request.form["minute"])
            second = int(request.form["second"])
            global \
                CLOCK_HOUR_HAND_POSITION, \
                CLOCK_MINUTE_HAND_POSITION, \
                CLOCK_SECOND_HAND_POSITION
            CLOCK_HOUR_HAND_POSITION = hour
            CLOCK_MINUTE_HAND_POSITION = minute
            CLOCK_SECOND_HAND_POSITION = second
            return redirect(url_for("config"))
        elif "set_ntp" in request.form:
            ntp_server = request.form["ntp_server"]
            ntp_sync_interval = int(request.form["ntp_sync_interval"])
            NTP_SERVER = ntp_server
            NTP_SYNC_INTERVAL = ntp_sync_interval
            return redirect(url_for("config"))
    return render_template(
        "config.html",
        ntp_server=NTP_SERVER,
        ntp_sync_interval=NTP_SYNC_INTERVAL,
        clock_hour=CLOCK_HOUR_HAND_POSITION,
        clock_minute=CLOCK_MINUTE_HAND_POSITION,
        clock_second=CLOCK_SECOND_HAND_POSITION,
    )


@app.route("/api/current_time", methods=["GET"])
def get_current_time():
    rtc_time = get_rtc_time()
    if rtc_time:
        return {"hour": rtc_time[0], "minute": rtc_time[1], "second": rtc_time[2]}
    return {"error": "Failed to get current time"}, 500


@app.route("/api/clock_time", methods=["GET"])
def get_clock_time():
    return {
        "hour": CLOCK_HOUR_HAND_POSITION,
        "minute": CLOCK_MINUTE_HAND_POSITION,
        "second": CLOCK_SECOND_HAND_POSITION,
    }


@app.route("/api/set_clock_time", methods=["POST"])
def set_clock_time():
    data = request.json
    hour = data.get("hour")
    minute = data.get("minute")
    second = data.get("second")
    if hour is None or minute is None or second is None:
        return {"error": "Invalid input"}, 400
    global \
        CLOCK_HOUR_HAND_POSITION, \
        CLOCK_MINUTE_HAND_POSITION, \
        CLOCK_SECOND_HAND_POSITION
    CLOCK_HOUR_HAND_POSITION = hour
    CLOCK_MINUTE_HAND_POSITION = minute
    CLOCK_SECOND_HAND_POSITION = second
    initial_time = datetime.now().replace(
        hour=hour, minute=minute, second=second, microsecond=0
    )
    set_rtc_time(initial_time)
    return {"message": "Clock time set successfully"}


@app.route("/api/ntp_server", methods=["POST"])
def set_ntp_server():
    global NTP_SERVER
    data = request.json
    ntp_server = data.get("ntp_server")
    if not ntp_server:
        return {"error": "Invalid input"}, 400
    NTP_SERVER = ntp_server
    return {"message": "NTP server updated successfully"}


@app.route("/api/ntp_settings", methods=["POST"])
def set_ntp_settings():
    global NTP_SERVER, NTP_SYNC_INTERVAL
    data = request.json
    ntp_server = data.get("ntp_server")
    ntp_sync_interval = data.get("ntp_sync_interval")
    if not ntp_server or ntp_sync_interval is None:
        return {"error": "Invalid input"}, 400
    NTP_SERVER = ntp_server
    NTP_SYNC_INTERVAL = int(ntp_sync_interval)
    return {"message": "NTP settings updated successfully"}


@app.route("/api/time_difference", methods=["GET"])
def get_time_difference():
    rtc_time = get_rtc_time()
    if rtc_time:
        total_seconds_diff = calculate_time_difference(
            rtc_time[0], rtc_time[1], rtc_time[2]
        )
        return {"time_difference_seconds": total_seconds_diff}
    return {"error": "Failed to get time difference"}, 500


@app.route("/api/ntp_drift", methods=["GET"])
def get_ntp_drift():
    try:
        ntp_client = ntplib.NTPClient()
        ntp_response = ntp_client.request(NTP_SERVER, version=3, port=123)
        return {"ntp_offset_seconds": ntp_response.offset}
    except Exception as e:
        return {"error": f"Failed to get NTP offset: {e}"}, 500


@app.route("/api/pause_clock", methods=["POST"])
def pause_clock():
    global paused
    paused = True
    return {"message": "Clock paused successfully"}


@app.route("/api/resume_clock", methods=["POST"])
def resume_clock():
    global paused
    paused = False
    return {"message": "Clock resumed successfully"}


@app.route("/api/clock_status", methods=["GET"])
def get_clock_status():
    global paused, fast_forward, reverse
    if paused:
        status = "Paused"
    elif fast_forward:
        status = "Fast Forward"
    elif reverse:
        status = "Reverse"
    else:
        status = "Ticking"
    return {"status": status}


def signal_handler(signum, frame):
    logging.info("Signal received, cleaning up GPIO and exiting...")
    GPIO.cleanup()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    global \
        CLOCK_HOUR_HAND_POSITION, \
        CLOCK_MINUTE_HAND_POSITION, \
        CLOCK_SECOND_HAND_POSITION

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
