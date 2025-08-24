function padZero(value) {
    return value.toString().padStart(2, '0');
}

let updateInterval;
let statusInterval;

function updateTimes() {
    Promise.all([
        fetch('/api/current_time').then(response => response.json()),
        fetch('/api/clock_time').then(response => response.json()),
        fetch('/api/time_difference').then(response => response.json()),
        fetch('/api/ntp_drift').then(response => response.json())
    ]).then(([currentTime, clockTime, timeDiff, ntpDrift]) => {
        if (!currentTime.error) {
            document.getElementById('ntp-time').textContent = 
                `${padZero(currentTime.hour)}:${padZero(currentTime.minute)}:${padZero(currentTime.second)}`;
        }
        
        document.getElementById('clock-time').textContent = 
            `${padZero(clockTime.hour)}:${padZero(clockTime.minute)}:${padZero(clockTime.second)}`;
        
        if (!timeDiff.error) {
            document.getElementById('time-difference').textContent = `${timeDiff.time_difference_seconds} seconds`;
        }
        
        if (!ntpDrift.error) {
            document.getElementById('ntp-offset').textContent = `${ntpDrift.ntp_offset_seconds} seconds`;
        }
    }).catch(error => {
        console.error('Error updating times:', error);
    });
}

function updateClockStatus() {
    fetch('/api/clock_status')
        .then(response => response.json())
        .then(data => {
            const statusText = data.status || 'Unknown';
            document.getElementById('clock-status').textContent = statusText;
        })
        .catch(error => {
            console.error('Error fetching clock status:', error);
        });
}

function pauseClock() {
    fetch('/api/pause_clock', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                updateClockStatus();
            } else {
                console.error('Error pausing clock:', data.error);
            }
        })
        .catch(error => {
            console.error('Error pausing clock:', error);
        });
}

function resumeClock() {
    fetch('/api/resume_clock', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                updateClockStatus();
            } else {
                console.error('Error resuming clock:', data.error);
            }
        })
        .catch(error => {
            console.error('Error resuming clock:', error);
        });
}

function initializeSettings() {
    Promise.all([
        fetch('/api/current_time').then(response => response.json()),
        fetch('/api/ntp_settings').then(response => response.json())
    ]).then(([currentTime, ntpSettings]) => {
        if (!currentTime.error) {
            const hourInput = document.getElementById('current-hour');
            const minuteInput = document.getElementById('current-minute');
            const secondInput = document.getElementById('current-second');
            
            if (hourInput) hourInput.value = padZero(currentTime.hour);
            if (minuteInput) minuteInput.value = padZero(currentTime.minute);
            if (secondInput) secondInput.value = padZero(currentTime.second);
        }
        
        if (!ntpSettings.error) {
            const ntpServerInput = document.getElementById('ntp-server');
            const ntpPortInput = document.getElementById('ntp-port');
            
            if (ntpServerInput) ntpServerInput.value = ntpSettings.ntp_server;
            if (ntpPortInput) ntpPortInput.value = ntpSettings.ntp_sync_interval;
        }
    }).catch(error => {
        console.error('Error initializing settings:', error);
    });
}

function startUpdates() {
    updateTimes();
    updateClockStatus();
    
    updateInterval = setInterval(updateTimes, 1000);
    statusInterval = setInterval(updateClockStatus, 1000);
}

function stopUpdates() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
    if (statusInterval) {
        clearInterval(statusInterval);
        statusInterval = null;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    startUpdates();
    initializeSettings();
});

window.addEventListener('beforeunload', function() {
    stopUpdates();
});