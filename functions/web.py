from datetime import datetime

import ntplib
from flask import redirect, render_template, request, url_for

# This class is designed to integrate with the Flask app and provide web interfaces
# for controlling the PiClock system


class WebUI:
    """
    Web interface for PiClock

    Provides web routes and API endpoints for interacting with the clock system.
    """

    def __init__(self, app, clock, ntp, rtc, fram, ntp_config):
        """
        Initialize the WebUI with references to the necessary objects

        Args:
            app: Flask application instance
            clock: CLOCK instance
            ntp: NTP instance
            rtc: RTC instance
            fram: FRAM instance
            ntp_config: Dict containing NTP configuration (server, port, sync_interval)
        """
        self.app = app
        self.clock = clock
        self.ntp = ntp
        self.rtc = rtc
        self.fram = fram
        self.ntp_server = ntp_config.get("server", "time.nist.gov")
        self.ntp_port = ntp_config.get("port", 123)
        self.ntp_sync_interval = ntp_config.get("sync_interval", 300)

        # Register all routes
        self._register_routes()

    def _register_routes(self):
        """Register all web routes with the Flask app"""
        # Web UI routes
        self.app.add_url_rule("/", "index", self.index, methods=["GET", "POST"])
        self.app.add_url_rule("/config", "config", self.config, methods=["GET", "POST"])

        # API routes
        self.app.add_url_rule(
            "/api/current_time", "get_current_time", self.get_current_time
        )
        self.app.add_url_rule("/api/clock_time", "get_clock_time", self.get_clock_time)
        self.app.add_url_rule(
            "/api/set_clock_time",
            "set_clock_time",
            self.set_clock_time,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/ntp_server", "set_ntp_server", self.set_ntp_server, methods=["POST"]
        )
        self.app.add_url_rule(
            "/api/ntp_settings",
            "set_ntp_settings",
            self.set_ntp_settings,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/time_difference", "get_time_difference", self.get_time_difference
        )
        self.app.add_url_rule("/api/ntp_drift", "get_ntp_drift", self.get_ntp_drift)
        self.app.add_url_rule(
            "/api/pause_clock", "pause_clock", self.pause_clock, methods=["POST"]
        )
        self.app.add_url_rule(
            "/api/resume_clock", "resume_clock", self.resume_clock, methods=["POST"]
        )
        self.app.add_url_rule(
            "/api/clock_status", "get_clock_status", self.get_clock_status
        )

    # Web UI route handlers
    def index(self):
        """Home page route handler"""
        if request.method == "POST":
            if "set_time" in request.form:
                hour = int(request.form["hour"])
                minute = int(request.form["minute"])
                second = int(request.form["second"])

                # Update clock position
                self.clock.hour_hand_position = hour
                self.clock.minute_hand_position = minute
                self.clock.second_hand_position = second

                # Set RTC time
                initial_time = datetime.now().replace(
                    hour=hour, minute=minute, second=second, microsecond=0
                )
                self.rtc.set_rtc_time(initial_time)
                return redirect(url_for("config"))

            elif "set_ntp" in request.form:
                self.ntp_server = request.form["ntp_server"]
                self.ntp_sync_interval = int(request.form["ntp_sync_interval"])

                # Update NTP configuration
                self.ntp.server = self.ntp_server
                self.ntp.sync_interval = self.ntp_sync_interval

                return redirect(url_for("config"))

        return render_template(
            "index.html",
            ntp_server=self.ntp_server,
            ntp_sync_interval=self.ntp_sync_interval,
        )

    def config(self):
        """Configuration page route handler"""
        if request.method == "POST":
            if "set_time" in request.form:
                hour = int(request.form["hour"])
                minute = int(request.form["minute"])
                second = int(request.form["second"])

                # Update clock position
                self.clock.hour_hand_position = hour
                self.clock.minute_hand_position = minute
                self.clock.second_hand_position = second

                return redirect(url_for("config"))

            elif "set_ntp" in request.form:
                self.ntp_server = request.form["ntp_server"]
                self.ntp_sync_interval = int(request.form["ntp_sync_interval"])

                # Update NTP configuration
                self.ntp.server = self.ntp_server
                self.ntp.sync_interval = self.ntp_sync_interval

                return redirect(url_for("config"))

        return render_template(
            "config.html",
            ntp_server=self.ntp_server,
            ntp_sync_interval=self.ntp_sync_interval,
            clock_hour=self.clock.hour_hand_position,
            clock_minute=self.clock.minute_hand_position,
            clock_second=self.clock.second_hand_position,
        )

    # API route handlers
    def get_current_time(self):
        """API endpoint to get current RTC time"""
        rtc_time = self.rtc.get_rtc_time()
        if rtc_time:
            return {"hour": rtc_time[0], "minute": rtc_time[1], "second": rtc_time[2]}
        return {"error": "Failed to get current time"}, 500

    def get_clock_time(self):
        """API endpoint to get current clock position"""
        return {
            "hour": self.clock.hour_hand_position,
            "minute": self.clock.minute_hand_position,
            "second": self.clock.second_hand_position,
        }

    def set_clock_time(self):
        """API endpoint to set clock time"""
        data = request.json
        hour = data.get("hour")
        minute = data.get("minute")
        second = data.get("second")

        if hour is None or minute is None or second is None:
            return {"error": "Invalid input"}, 400

        # Update clock position
        self.clock.hour_hand_position = hour
        self.clock.minute_hand_position = minute
        self.clock.second_hand_position = second

        # Set RTC time
        initial_time = datetime.now().replace(
            hour=hour, minute=minute, second=second, microsecond=0
        )
        self.rtc.set_rtc_time(initial_time)

        return {"message": "Clock time set successfully"}

    def set_ntp_server(self):
        """API endpoint to update NTP server"""
        data = request.json
        ntp_server = data.get("ntp_server")

        if not ntp_server:
            return {"error": "Invalid input"}, 400

        self.ntp_server = ntp_server
        self.ntp.server = ntp_server

        return {"message": "NTP server updated successfully"}

    def set_ntp_settings(self):
        """API endpoint to update NTP settings"""
        data = request.json
        ntp_server = data.get("ntp_server")
        ntp_sync_interval = data.get("ntp_sync_interval")

        if not ntp_server or ntp_sync_interval is None:
            return {"error": "Invalid input"}, 400

        self.ntp_server = ntp_server
        self.ntp_sync_interval = int(ntp_sync_interval)

        # Update NTP configuration
        self.ntp.server = ntp_server
        self.ntp.sync_interval = int(ntp_sync_interval)

        return {"message": "NTP settings updated successfully"}

    def get_time_difference(self):
        """API endpoint to get time difference between RTC and clock"""
        rtc_time = self.rtc.get_rtc_time()
        if rtc_time:
            total_seconds_diff = self.clock.calculate_time_difference(
                rtc_time[0], rtc_time[1], rtc_time[2]
            )
            return {"time_difference_seconds": total_seconds_diff}
        return {"error": "Failed to get time difference"}, 500

    def get_ntp_drift(self):
        """API endpoint to get NTP drift"""
        try:
            ntp_client = ntplib.NTPClient()
            ntp_response = ntp_client.request(
                self.ntp_server, version=3, port=self.ntp_port
            )
            return {"ntp_offset_seconds": ntp_response.offset}
        except Exception as e:
            return {"error": f"Failed to get NTP offset: {e}"}, 500

    def pause_clock(self):
        """API endpoint to pause the clock"""
        self.clock.paused = True
        return {"message": "Clock paused successfully"}

    def resume_clock(self):
        """API endpoint to resume the clock"""
        self.clock.paused = False
        return {"message": "Clock resumed successfully"}

    def get_clock_status(self):
        """API endpoint to get clock status"""
        if self.clock.paused:
            status = "Paused"
        elif self.clock.fast_forward:
            status = "Fast Forward"
        elif self.clock.reverse:
            status = "Reverse"
        else:
            status = "Ticking"
        return {"status": status}
