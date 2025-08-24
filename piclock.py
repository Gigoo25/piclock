import logging
import signal
import sys
import threading
import time
import json
import os
from datetime import datetime
from typing import Optional, Tuple

try:
    import adafruit_ds3231
    import adafruit_fram
    import board
    import ntplib
    import RPi.GPIO as GPIO
    HARDWARE_AVAILABLE = True
except ImportError:
    print("Hardware modules not available, running in simulation mode")
    HARDWARE_AVAILABLE = False
from flask import Flask, redirect, render_template, request, url_for

class ClockController:
    def __init__(self):
        # GPIO Configuration
        self.tick_pin1 = 12
        self.tick_pin2 = 13
        
        # NTP Configuration
        self.ntp_server = "time.nist.gov"
        self.ntp_sync_interval = 300  # 5 minutes
        
        # Flask Configuration
        self.flask_host = "0.0.0.0"
        self.flask_port = 5000
        
        # Clock state
        self.current_tick_pin = self.tick_pin1
        self.fast_forward = False
        self.paused = False
        self.reverse = False
        
        # Clock position
        self.clock_hour = None
        self.clock_minute = None
        self.clock_second = None
        
        # Threading
        self.lock = threading.Lock()
        self.clock_position_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        
        # Hardware initialization
        self.hardware_available = HARDWARE_AVAILABLE
        self.rtc = None
        self.fram = None
        self._init_hardware()
        
        # Flask app
        self.app = Flask(__name__, static_url_path="/static")
        self._setup_flask_routes()
        
        # Signal handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _init_hardware(self):
        if self.hardware_available:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.tick_pin1, GPIO.OUT)
            GPIO.setup(self.tick_pin2, GPIO.OUT)
            GPIO.output(self.tick_pin1, GPIO.LOW)
            GPIO.output(self.tick_pin2, GPIO.LOW)
            
            try:
                i2c = board.I2C()
                self.rtc = adafruit_ds3231.DS3231(i2c)
                self.fram = adafruit_fram.FRAM_I2C(i2c)
                logging.info("I2C devices initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize I2C devices: {e}")
                logging.error("Hardware operations will fail")
                self.hardware_available = False
                self.rtc = None
                self.fram = None
    
    def set_rtc_time(self, time_data):
        if not self.hardware_available or not self.rtc:
            logging.error("Cannot set RTC time - hardware not available")
            return
        try:
            self.rtc.datetime = time_data.timetuple()
        except Exception as e:
            logging.error(f"Failed to set RTC time: {e}")
    
    def get_rtc_time(self) -> Optional[Tuple[int, int, int]]:
        if not self.hardware_available or not self.rtc:
            logging.error("Cannot get RTC time - hardware not available")
            return None
        try:
            rtc_time = self.rtc.datetime
            return rtc_time.tm_hour, rtc_time.tm_min, rtc_time.tm_sec
        except Exception as e:
            logging.error(f"Failed to get RTC time: {e}")
            return None
    
    def write_time_to_fram(self):
        if not self.hardware_available or not self.fram:
            logging.error("Cannot write to FRAM - hardware not available")
            return
        try:
            with self.clock_position_lock:
                time_string = f"{self.clock_hour:02}:{self.clock_minute:02}:{self.clock_second:02}"
            self.fram[0:8] = bytearray(time_string.encode("utf-8"))
            logging.info(f"Wrote clock time '{time_string}' to FRAM.")
        except Exception as e:
            logging.error(f"Failed to write time to FRAM: {e}")
    
    def read_time_from_fram(self) -> Optional[str]:
        if not self.hardware_available or not self.fram:
            logging.error("Cannot read from FRAM - hardware not available")
            return None
        try:
            time_bytes = self.fram[0:8]
            time_string = time_bytes.decode("utf-8")
            
            if len(time_string) != 8 or time_string[2] != ':' or time_string[5] != ':':
                logging.warning(f"Invalid time format in FRAM: {time_string}")
                return None
                
            hour, minute, second = map(int, time_string.split(":"))
            if not (1 <= hour <= 12) or not (0 <= minute <= 59) or not (0 <= second <= 59):
                logging.warning(f"Invalid time values in FRAM: {time_string}")
                return None
                
            logging.info(f"Read time from FRAM at address 0: {time_string}")
            return time_string
        except Exception as e:
            logging.error(f"Failed to read time from FRAM: {e}")
            return None
    
    def sync_rtc_time_with_ntp_time(self, on_startup=False):
        try:
            ntp_time = self.get_ntp_time()
            if ntp_time:
                self.set_rtc_time(ntp_time)
                if on_startup:
                    logging.info("RTC time synchronized with NTP time on startup")
        except Exception as e:
            logging.error(f"Failed to sync RTC time with NTP time: {e}")
    
    def continuous_sync_rtc_time_with_ntp_time(self):
        while not self.shutdown_event.is_set():
            self.sync_rtc_time_with_ntp_time()
            sync_interval = max(1, self.ntp_sync_interval)
            for _ in range(sync_interval):
                if self.shutdown_event.is_set():
                    break
                time.sleep(1)
    
    def get_ntp_time(self) -> Optional[datetime]:
        try:
            ntp_client = ntplib.NTPClient()
            ntp_response = ntp_client.request(self.ntp_server, version=3, port=123)
            return datetime.fromtimestamp(ntp_response.tx_time)
        except Exception as e:
            logging.error(f"Failed to get NTP time: {e}")
            return None
    
    def send_pulse(self, pin, duration, next_tick_delay=0):
        if not self.hardware_available:
            logging.error(f"Cannot send GPIO pulse - hardware not available")
            return
            
        try:
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(duration)
            GPIO.output(pin, GPIO.LOW)
            time.sleep(next_tick_delay)
        except Exception as e:
            logging.error(f"GPIO operation failed for pin {pin}: {e}")
    
    def forward_tick(self):
        self.reverse = False
        self.send_pulse(self.current_tick_pin, 0.1)
        self.current_tick_pin = self.tick_pin2 if self.current_tick_pin == self.tick_pin1 else self.tick_pin1
        self.update_clock_position()
    
    def reverse_tick(self):
        self.reverse = True
        self.send_pulse(self.current_tick_pin, 0.01)
        self.current_tick_pin = self.tick_pin1 if self.current_tick_pin == self.tick_pin2 else self.tick_pin2
        self.send_pulse(self.current_tick_pin, 0.03)
        self.update_clock_position(reverse=True)
    
    def calculate_time_difference(self, ntp_hour, ntp_minute, ntp_second):
        with self.clock_position_lock:
            clock_hour = self.clock_hour
            clock_minute = self.clock_minute
            clock_second = self.clock_second

        ntp_total_seconds = ntp_hour * 3600 + ntp_minute * 60 + ntp_second
        
        clock_hour_24 = clock_hour
        if clock_hour == 12:
            clock_hour_24 = 0 if ntp_hour < 12 else 12
        elif ntp_hour >= 12:
            clock_hour_24 = clock_hour + 12
        
        clock_total_seconds = clock_hour_24 * 3600 + clock_minute * 60 + clock_second
        total_seconds_diff = ntp_total_seconds - clock_total_seconds

        if total_seconds_diff > 21600:
            total_seconds_diff -= 43200
        elif total_seconds_diff < -21600:
            total_seconds_diff += 43200

        return total_seconds_diff
    
    def update_clock_position(self, reverse=False):
        with self.clock_position_lock:
            if reverse:
                self.clock_second = (self.clock_second - 1) % 60
                if self.clock_second == 59:
                    self.clock_minute = (self.clock_minute - 1) % 60
                    if self.clock_minute == 59:
                        self.clock_hour = (self.clock_hour - 1) % 12
                        if self.clock_hour == 0:
                            self.clock_hour = 12
            else:
                self.clock_second = (self.clock_second + 1) % 60
                if self.clock_second == 0:
                    self.clock_minute = (self.clock_minute + 1) % 60
                    if self.clock_minute == 0:
                        self.clock_hour = (self.clock_hour + 1) % 12
                        if self.clock_hour == 0:
                            self.clock_hour = 12
    
    def synchronize_clock(self):
        rtc_time = self.get_rtc_time()
        if not rtc_time:
            return
            
        hour, minute, second = rtc_time
        total_seconds_diff = self.calculate_time_difference(hour, minute, second)

        logging.info(f"RTC time: {hour:02}:{minute:02}:{second:02}")
        logging.info(f"Clock time: {self.clock_hour:02}:{self.clock_minute:02}:{self.clock_second:02}")

        tolerance = 1

        if abs(total_seconds_diff) <= tolerance:
            logging.info("Clock is in sync with RTC time")
            self.fast_forward = False
            self.forward_tick()
        elif total_seconds_diff > tolerance:
            logging.info(f"Clock is behind RTC time by {total_seconds_diff} seconds")
            self.fast_forward = True
            self.forward_tick()
        else:
            logging.info(f"Clock is ahead of RTC time by {abs(total_seconds_diff)} seconds")
            self.fast_forward = False
            self.reverse_tick()
    
    def timer_callback(self, tick_event):
        while not self.shutdown_event.is_set():
            time.sleep(0.25 if self.fast_forward else 1)
            if self.shutdown_event.is_set():
                break
            with self.lock:
                if not self.paused:
                    tick_event.set()
    
    def _signal_handler(self, signum, frame):
        logging.info("Signal received, initiating graceful shutdown...")
        self.shutdown_event.set()
        logging.info("Shutdown signal sent to all threads")
        time.sleep(1)
        logging.info("Cleaning up GPIO and exiting...")
        if self.hardware_available:
            try:
                GPIO.cleanup()
            except Exception as e:
                logging.error(f"Error during GPIO cleanup: {e}")
        sys.exit(0)
    
    def _setup_flask_routes(self):
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)
        
        @self.app.route("/", methods=["GET", "POST"])
        def index():
            if request.method == "POST":
                if "set_time" in request.form:
                    try:
                        hour = int(request.form["hour"])
                        minute = int(request.form["minute"])
                        second = int(request.form["second"])
                        
                        if not (1 <= hour <= 12) or not (0 <= minute <= 59) or not (0 <= second <= 59):
                            return "Invalid time values", 400
                        
                        with self.clock_position_lock:
                            self.clock_hour = hour
                            self.clock_minute = minute
                            self.clock_second = second
                        
                        initial_time = datetime.now().replace(hour=hour, minute=minute, second=second, microsecond=0)
                        self.set_rtc_time(initial_time)
                        return redirect(url_for("config"))
                    except (ValueError, KeyError):
                        return "Invalid input", 400
                elif "set_ntp" in request.form:
                    try:
                        ntp_server = request.form["ntp_server"].strip()
                        ntp_sync_interval = int(request.form["ntp_sync_interval"])
                        
                        if not ntp_server or ntp_sync_interval < 1:
                            return "Invalid NTP settings", 400
                        
                        self.ntp_server = ntp_server
                        self.ntp_sync_interval = ntp_sync_interval
                        return redirect(url_for("config"))
                    except (ValueError, KeyError):
                        return "Invalid input", 400
            return render_template("index.html", ntp_server=self.ntp_server, ntp_sync_interval=self.ntp_sync_interval)

        @self.app.route("/config", methods=["GET", "POST"])
        def config():
            if request.method == "POST":
                if "set_time" in request.form:
                    try:
                        hour = int(request.form["hour"])
                        minute = int(request.form["minute"])
                        second = int(request.form["second"])
                        
                        if not (1 <= hour <= 12) or not (0 <= minute <= 59) or not (0 <= second <= 59):
                            return "Invalid time values", 400
                        
                        with self.clock_position_lock:
                            self.clock_hour = hour
                            self.clock_minute = minute
                            self.clock_second = second
                        return redirect(url_for("config"))
                    except (ValueError, KeyError):
                        return "Invalid input", 400
                elif "set_ntp" in request.form:
                    try:
                        ntp_server = request.form["ntp_server"].strip()
                        ntp_sync_interval = int(request.form["ntp_sync_interval"])
                        
                        if not ntp_server or ntp_sync_interval < 1:
                            return "Invalid NTP settings", 400
                        
                        self.ntp_server = ntp_server
                        self.ntp_sync_interval = ntp_sync_interval
                        return redirect(url_for("config"))
                    except (ValueError, KeyError):
                        return "Invalid input", 400
            with self.clock_position_lock:
                return render_template(
                    "config.html",
                    ntp_server=self.ntp_server,
                    ntp_sync_interval=self.ntp_sync_interval,
                    clock_hour=self.clock_hour,
                    clock_minute=self.clock_minute,
                    clock_second=self.clock_second,
                )

        @self.app.route("/api/current_time", methods=["GET"])
        def get_current_time():
            rtc_time = self.get_rtc_time()
            if rtc_time:
                return {"hour": rtc_time[0], "minute": rtc_time[1], "second": rtc_time[2]}
            return {"error": "Failed to get current time"}, 500

        @self.app.route("/api/clock_time", methods=["GET"])
        def get_clock_time():
            with self.clock_position_lock:
                return {
                    "hour": self.clock_hour,
                    "minute": self.clock_minute,
                    "second": self.clock_second,
                }

        @self.app.route("/api/set_clock_time", methods=["POST"])
        def set_clock_time():
            try:
                data = request.get_json()
                if not data:
                    return {"error": "Invalid JSON"}, 400
                    
                hour = data.get("hour")
                minute = data.get("minute")
                second = data.get("second")
                
                if hour is None or minute is None or second is None:
                    return {"error": "Missing required fields"}, 400
                
                try:
                    hour = int(hour)
                    minute = int(minute)
                    second = int(second)
                except (ValueError, TypeError):
                    return {"error": "Invalid time values - must be integers"}, 400
                
                if not (1 <= hour <= 12):
                    return {"error": "Hour must be between 1 and 12"}, 400
                if not (0 <= minute <= 59):
                    return {"error": "Minute must be between 0 and 59"}, 400
                if not (0 <= second <= 59):
                    return {"error": "Second must be between 0 and 59"}, 400
                
                with self.clock_position_lock:
                    self.clock_hour = hour
                    self.clock_minute = minute
                    self.clock_second = second
                
                initial_time = datetime.now().replace(hour=hour, minute=minute, second=second, microsecond=0)
                self.set_rtc_time(initial_time)
                return {"message": "Clock time set successfully"}
            except Exception as e:
                logging.error(f"Error in set_clock_time: {e}")
                return {"error": "Internal server error"}, 500

        @self.app.route("/api/ntp_server", methods=["POST"])
        def set_ntp_server():
            try:
                data = request.get_json()
                if not data:
                    return {"error": "Invalid JSON"}, 400
                    
                ntp_server = data.get("ntp_server", "").strip()
                if not ntp_server:
                    return {"error": "Invalid input"}, 400
                self.ntp_server = ntp_server
                return {"message": "NTP server updated successfully"}
            except Exception as e:
                logging.error(f"Error in set_ntp_server: {e}")
                return {"error": "Internal server error"}, 500

        @self.app.route("/api/ntp_settings", methods=["GET"])
        def get_ntp_settings():
            return {
                "ntp_server": self.ntp_server,
                "ntp_sync_interval": self.ntp_sync_interval
            }

        @self.app.route("/api/ntp_settings", methods=["POST"])
        def set_ntp_settings():
            try:
                data = request.get_json()
                if not data:
                    return {"error": "Invalid JSON"}, 400
                    
                ntp_server = data.get("ntp_server", "").strip()
                ntp_sync_interval = data.get("ntp_sync_interval")
                
                if not ntp_server or ntp_sync_interval is None:
                    return {"error": "Missing required fields"}, 400
                
                try:
                    ntp_sync_interval = int(ntp_sync_interval)
                    if ntp_sync_interval < 1:
                        return {"error": "NTP sync interval must be at least 1 second"}, 400
                except (ValueError, TypeError):
                    return {"error": "Invalid NTP sync interval - must be a positive integer"}, 400
                
                self.ntp_server = ntp_server
                self.ntp_sync_interval = ntp_sync_interval
                return {"message": "NTP settings updated successfully"}
            except Exception as e:
                logging.error(f"Error in set_ntp_settings: {e}")
                return {"error": "Internal server error"}, 500

        @self.app.route("/api/time_difference", methods=["GET"])
        def get_time_difference():
            rtc_time = self.get_rtc_time()
            if rtc_time:
                total_seconds_diff = self.calculate_time_difference(rtc_time[0], rtc_time[1], rtc_time[2])
                return {"time_difference_seconds": total_seconds_diff}
            return {"error": "Failed to get time difference"}, 500

        @self.app.route("/api/ntp_drift", methods=["GET"])
        def get_ntp_drift():
            try:
                ntp_client = ntplib.NTPClient()
                ntp_response = ntp_client.request(self.ntp_server, version=3, port=123)
                return {"ntp_offset_seconds": ntp_response.offset}
            except Exception as e:
                return {"error": f"Failed to get NTP offset: {e}"}, 500

        @self.app.route("/api/pause_clock", methods=["POST"])
        def pause_clock():
            self.paused = True
            return {"message": "Clock paused successfully"}

        @self.app.route("/api/resume_clock", methods=["POST"])
        def resume_clock():
            self.paused = False
            return {"message": "Clock resumed successfully"}

        @self.app.route("/api/clock_status", methods=["GET"])
        def get_clock_status():
            if self.paused:
                status = "Paused"
            elif self.fast_forward:
                status = "Fast Forward"
            elif self.reverse:
                status = "Reverse"
            else:
                status = "Ticking"
            return {"status": status}
    
    def run(self):
        tick_event = threading.Event()

        time_string = self.read_time_from_fram()
        if time_string:
            hour, minute, second = map(int, time_string.split(":"))
            with self.clock_position_lock:
                self.clock_hour = hour % 12 or 12
                self.clock_minute = minute
                self.clock_second = second

        self.sync_rtc_time_with_ntp_time(on_startup=True)

        timer_thread = threading.Thread(target=self.timer_callback, args=(tick_event,))
        timer_thread.daemon = True
        timer_thread.start()

        sync_timer_thread = threading.Thread(target=self.continuous_sync_rtc_time_with_ntp_time)
        sync_timer_thread.daemon = True
        sync_timer_thread.start()

        flask_thread = threading.Thread(
            target=self.app.run, 
            kwargs={
                "host": self.flask_host, 
                "port": self.flask_port
            }
        )
        flask_thread.daemon = True
        flask_thread.start()

        try:
            while not self.shutdown_event.is_set():
                tick_event.wait(timeout=1)
                if self.shutdown_event.is_set():
                    break
                with self.lock:
                    tick_event.clear()
                    self.synchronize_clock()
                    self.write_time_to_fram()
        except (KeyboardInterrupt, SystemExit):
            self._signal_handler(None, None)

def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    clock_controller = ClockController()
    clock_controller.run()

if __name__ == "__main__":
    main()
