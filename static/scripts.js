function padZero(value) {
    return value.toString().padStart(2, '0');
}

function updateTimes() {
    fetch('/api/current_time')
        .then(response => response.json())
        .then(data => {
            if (!data.error) {
                document.getElementById('ntp-time').textContent = `${padZero(data.hour)}:${padZero(data.minute)}:${padZero(data.second)}`;
            }
        });

    fetch('/api/clock_time')
        .then(response => response.json())
        .then(data => {
            document.getElementById('clock-time').textContent = `${padZero(data.hour)}:${padZero(data.minute)}:${padZero(data.second)}`;
        });

    fetch('/api/time_difference')
        .then(response => response.json())
        .then(data => {
            if (!data.error) {
                document.getElementById('time-difference').textContent = `${data.time_difference_seconds} seconds`;
            }
        });

    fetch('/api/ntp_drift')
        .then(response => response.json())
        .then(data => {
            if (!data.error) {
                document.getElementById('ntp-offset').textContent = `${data.ntp_offset_seconds} seconds`;
            }
        });
}

function updateClockStatus() {
    fetch('/api/clock_status')
        .then(response => response.json())
        .then(data => {
            let statusText;
            switch (data.status) {
                case 'Fast Forward':
                    statusText = 'Fast Forward';
                    break;
                case 'Reverse':
                    statusText = 'Reverse';
                    break;
                case 'Ticking':
                    statusText = 'Ticking';
                    break;
                case 'Paused':
                    statusText = 'Paused';
                    break;
                default:
                    statusText = 'Unknown';
            }
            document.getElementById('clock-status').textContent = statusText;
        })
        .catch(error => alert('Error fetching clock status: ' + error));
}

function pauseClock() {
    fetch('/api/pause_clock', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            updateClockStatus();
        })
        .catch(error => alert('Error pausing clock: ' + error));
}

function resumeClock() {
    fetch('/api/resume_clock', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            updateClockStatus();
        })
        .catch(error => alert('Error resuming clock: ' + error));
}

function setTime() {
    // Implement the logic for setting the time
    alert('Time set successfully!');
    document.querySelector('form.inline-form').submit();
}

function setNTP() {
    // Implement the logic for setting the NTP settings
    alert('NTP settings set successfully!');
    document.querySelector('form.inline-form').submit();
}

function initializeSettings() {
    fetch('/api/current_time')
        .then(response => response.json())
        .then(data => {
            if (!data.error) {
                document.getElementById('current-hour').value = padZero(data.hour);
                document.getElementById('current-minute').value = padZero(data.minute);
                document.getElementById('current-second').value = padZero(data.second);
            }
        });

    fetch('/api/ntp_settings')
        .then(response => response.json())
        .then(data => {
            if (!data.error) {
                document.getElementById('ntp-server').value = data.ntp_server;
                document.getElementById('ntp-port').value = data.ntp_sync_interval;
            }
        });
}

setInterval(updateTimes, 1000);
setInterval(updateClockStatus, 1000);
updateTimes();
updateClockStatus();
initializeSettings();