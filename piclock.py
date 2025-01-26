import argparse
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

# GPIO Constants
TICK_PIN1 = 12
TICK_PIN2 = 13

# NTP Constants
NTP_SYNC_INTERVAL = 300
NTP_SERVER = "time.nist.gov"

# Global variables
lock = threading.Lock()  # Create a lock for thread safety
current_tick_pin = TICK_PIN1  # Start with TICK_PIN1
fast_forward = False
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


def set_rtc_time(time_data):
    try:
        # Convert datetime to time.struct_time
        t = time_data.timetuple()
        rtc.datetime = t
    except Exception as e:
        print(f"Failed to set RTC time: {e}")


def get_rtc_time():
    try:
        rtc_time = rtc.datetime
        return rtc_time.tm_hour, rtc_time.tm_min, rtc_time.tm_sec
    except Exception as e:
        print(f"Failed to get RTC time: {e}")
        return None


def write_time_to_fram():
    try:
        # Format the clock time as a string (HH:MM:SS)
        time_string = f"{CLOCK_HOUR_HAND_POSITION:02}:{CLOCK_MINUTE_HAND_POSITION:02}:{CLOCK_SECOND_HAND_POSITION:02}"
        # Write the time string to FRAM at address 0
        fram[0:8] = bytearray(time_string.encode("utf-8"))  # Store as bytes
        print(f"Wrote clock time '{time_string}' to FRAM.")
    except Exception as e:
        print(f"Failed to write time to FRAM: {e}")


def read_time_from_fram():
    try:
        # Read the time string from FRAM at address 0
        time_bytes = fram[0:8]  # Read 8 bytes
        time_string = time_bytes.decode("utf-8")  # Convert bytes back to string
        print(f"Read time from FRAM at address 0: {time_string}")
        return time_string
    except Exception as e:
        print(f"Failed to read time from FRAM: {e}")
        return None


def sync_rtc_time_with_ntp_time(on_startup=False):
    try:
        ntp_time = get_ntp_time()
        if ntp_time is not None:
            set_rtc_time(ntp_time)

            if on_startup:
                print("RTC time synchronized with NTP time on startup")
            else:
                time.sleep(NTP_SYNC_INTERVAL)
    except ntplib.NTPException as e:
        print(f"Failed to get NTP time: {e}")
    except IOError as e:
        print(f"Failed to communicate with DS3231: {e}")
    except Exception as e:
        print(f"Failed to sync RTC time with NTP time: {e}")


def get_ntp_time():
    try:
        ntp_client = ntplib.NTPClient()
        ntp_response = ntp_client.request(NTP_SERVER, version=3, port=123)
        ntp_time = datetime.fromtimestamp(ntp_response.tx_time)
        return ntp_time
    except Exception as e:
        print(f"Failed to get NTP time: {e}")
        return None


def send_pulse(pin, duration, next_tick_delay=0):
    # Send a pulse of a specific duration on the given pin
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(next_tick_delay)


def forward_tick():
    # Forward: short pulse on the current pin while keeping it high for a short duration, then switch to the other pin
    global current_tick_pin
    send_pulse(current_tick_pin, 0.1)
    current_tick_pin = TICK_PIN2 if current_tick_pin == TICK_PIN1 else TICK_PIN1
    update_clock_position()


def reverse_tick():
    # Reverse: short pulse on the current pin while keeping it high for a short duration, then longer pulse on the other pin inversing the frequency signal
    global current_tick_pin
    send_pulse(current_tick_pin, 0.01)
    current_tick_pin = TICK_PIN1 if current_tick_pin == TICK_PIN2 else TICK_PIN2
    send_pulse(current_tick_pin, 0.03)
    update_clock_position(reverse=True)


def pulse_tick():
    # Pulse: short pulse on TICK_PIN1, then long pulse on TICK_PIN2 with a delay between them
    send_pulse(TICK_PIN1, 0.01, 0.5)
    send_pulse(TICK_PIN2, 0.03, 0.5)


def calculate_time_difference(ntp_hour, ntp_minute, ntp_second):
    # Convert 12-hour clock time to 24-hour format based on the closest AM or PM
    if CLOCK_HOUR_HAND_POSITION == 12:
        clock_hour_24 = 0 if ntp_hour < 12 else 12
    else:
        clock_hour_24 = CLOCK_HOUR_HAND_POSITION
        if ntp_hour >= 12:
            clock_hour_24 += 12

    # Calculate the time difference between the NTP time and the clock time
    ntp_total_seconds = ntp_hour * 3600 + ntp_minute * 60 + ntp_second
    clock_total_seconds = (
        clock_hour_24 * 3600
        + CLOCK_MINUTE_HAND_POSITION * 60
        + CLOCK_SECOND_HAND_POSITION
    )

    total_seconds_diff = ntp_total_seconds - clock_total_seconds

    # Handle wrap-around at midnight
    if total_seconds_diff > 21600:  # More than 6 hours ahead
        total_seconds_diff -= 43200  # Subtract 12 hours
    elif total_seconds_diff < -21600:  # More than 6 hours behind
        total_seconds_diff += 43200  # Add 12 hours

    return total_seconds_diff


def update_clock_position(reverse=False):
    global CLOCK_HOUR_HAND_POSITION
    global CLOCK_MINUTE_HAND_POSITION
    global CLOCK_SECOND_HAND_POSITION
    if reverse:
        # Remove 1 second from the clock time
        CLOCK_SECOND_HAND_POSITION = (CLOCK_SECOND_HAND_POSITION - 1) % 60
        if CLOCK_SECOND_HAND_POSITION == 59:
            CLOCK_MINUTE_HAND_POSITION = (CLOCK_MINUTE_HAND_POSITION - 1) % 60
            if CLOCK_MINUTE_HAND_POSITION == 59:
                CLOCK_HOUR_HAND_POSITION = (CLOCK_HOUR_HAND_POSITION - 1) % 12
    else:
        # Add 1 second to the clock time
        CLOCK_SECOND_HAND_POSITION = (CLOCK_SECOND_HAND_POSITION + 1) % 60
        if CLOCK_SECOND_HAND_POSITION == 0:
            CLOCK_MINUTE_HAND_POSITION = (CLOCK_MINUTE_HAND_POSITION + 1) % 60
            if CLOCK_MINUTE_HAND_POSITION == 0:
                CLOCK_HOUR_HAND_POSITION = (CLOCK_HOUR_HAND_POSITION + 1) % 12


def synchronize_clock():
    hour, minute, second = get_rtc_time()
    total_seconds_diff = calculate_time_difference(hour, minute, second)

    print(f"RTC time: {hour}:{minute}:{second}")
    print(
        f"Clock time: {CLOCK_HOUR_HAND_POSITION}:{CLOCK_MINUTE_HAND_POSITION}:{CLOCK_SECOND_HAND_POSITION}"
    )

    if hour is not None:
        tolerance = (
            1  # 1 second tolerance so we don't constantly fast forward or reverse
        )

        if abs(total_seconds_diff) <= tolerance:
            print("Clock is in sync with RTC time")
            set_fast_forward(False)
            forward_tick()
        elif total_seconds_diff > tolerance:
            print(f"Clock is behind RTC time by {total_seconds_diff} seconds")
            set_fast_forward(True)
            forward_tick()
        else:
            print(f"Clock is ahead of RTC time by {abs(total_seconds_diff)} seconds")
            set_fast_forward(False)
            reverse_tick()


def set_fast_forward(value):
    global fast_forward
    fast_forward = value


def timer_callback(tick_event):
    while True:
        if fast_forward:
            time.sleep(
                0.25
            )  # 4 times faster seems to be a safe value. Previous value was 0.1 and clocked seemed to be skipping seconds occasionally
        else:
            time.sleep(1)
        with lock:
            tick_event.set()


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run PiClock script")
    parser.add_argument(
        "--set-time",
        action="store_true",
        help="Override the current clock time with the provided hour, minute, and second.",
    )
    parser.add_argument("--hour", type=int, help="Current hour hand position (1-12)")
    parser.add_argument(
        "--minute", type=int, help="Current minute hand position (0-59)"
    )
    parser.add_argument(
        "--second", type=int, help="Current second hand position (0-59)"
    )
    args = parser.parse_args()

    if args.set_time:
        if args.hour is None or args.minute is None or args.second is None:
            parser.error(
                "--hour, --minute, and --second are required when --set-time is specified"
            )

    return args


def signal_handler(signum, frame):
    print("Signal received, cleaning up GPIO and exiting...")
    GPIO.cleanup()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)  # Handle CTRL + C
signal.signal(signal.SIGTSTP, signal_handler)  # Handle CTRL + Z


def main():
    global \
        CLOCK_HOUR_HAND_POSITION, \
        CLOCK_MINUTE_HAND_POSITION, \
        CLOCK_SECOND_HAND_POSITION

    tick_event = threading.Event()

    args = parse_arguments()
    CLOCK_HOUR_HAND_POSITION = args.hour
    CLOCK_MINUTE_HAND_POSITION = args.minute
    CLOCK_SECOND_HAND_POSITION = args.second

    if args.set_time:
        # Use the provided hour, minute, and second to set the initial time
        initial_time = datetime.now().replace(
            hour=args.hour, minute=args.minute, second=args.second, microsecond=0
        )
        set_rtc_time(initial_time)
    else:
        # Read the initial time from FRAM
        time_string = read_time_from_fram()
        if time_string:
            hour, minute, second = map(int, time_string.split(":"))
            CLOCK_HOUR_HAND_POSITION = hour % 12 or 12
            CLOCK_MINUTE_HAND_POSITION = minute
            CLOCK_SECOND_HAND_POSITION = second

    sync_rtc_time_with_ntp_time(on_startup=True)

    # Start the timer in a separate thread
    timer_thread = threading.Thread(target=timer_callback, args=(tick_event,))
    timer_thread.daemon = True
    timer_thread.start()

    # Sync the RTC time with the NTP time every 5 minutes in a separate thread
    sync_timer_thread = threading.Thread(target=sync_rtc_time_with_ntp_time)
    sync_timer_thread.daemon = True
    sync_timer_thread.start()

    while True:
        tick_event.wait()
        with lock:  # Use the lock to ensure thread safety
            tick_event.clear()
            synchronize_clock()
            write_time_to_fram()  # Save the time to FRAM every second


if __name__ == "__main__":
    main()
