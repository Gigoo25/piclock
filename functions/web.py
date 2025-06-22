from flask import redirect, render_template, request, url_for


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
