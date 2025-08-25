# PiClock - Production-Ready Raspberry Pi Analog Clock Controller

A robust Python application that drives an analog clock mechanism using a Raspberry Pi, RTC module, and NTP synchronization. Features a web interface for remote control and monitoring.

## Features

- **Accurate Timekeeping**: NTP synchronization with configurable servers
- **Advanced Pulsing**: Region-specific reverse logic and precise pulse control
- **Hardware Control**: GPIO-based clock mechanism control (forward, reverse, fast-forward)
- **Web Interface**: Flask-based dashboard for remote monitoring and control
- **Production Ready**: Proper logging, security hardening, error handling
- **Fault Tolerance**: Graceful error handling and recovery mechanisms
- **Self-Contained**: All files in one directory, no configuration files needed

## Bill of Materials

- Raspberry Pi (3B+ or newer recommended)
- Modified ticking clock mechanism
- DS3231 RTC module
- Adafruit I2C Non-Volatile FRAM Breakout (optional)
- Dupont wires

## System Requirements

- **OS**: Raspberry Pi OS (Bullseye or newer)
- **Python**: 3.11+
- **Hardware**: GPIO access, I2C support
- **Network**: Internet access for NTP synchronization

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/piclock.git
cd piclock

# Install dependencies
pip3 install -r requirements.txt

# Run the application
python3 piclock.py

## Service Installation

To run PiClock as a systemd service (recommended for production):

```bash
# Navigate to your PiClock directory
cd /path/to/your/piclock

# Install as a service (requires sudo)
sudo ./install_service.sh

# Start the service
sudo systemctl start piclock

# Check service status
sudo systemctl status piclock

# View logs
sudo journalctl -u piclock -f
```

**Note**: The installation script automatically detects your current directory and user, so you can install PiClock from any location on your system.

### Service Management

```bash
# Start the service
sudo systemctl start piclock

# Stop the service
sudo systemctl stop piclock

# Restart the service
sudo systemctl restart piclock

# Enable auto-start on boot
sudo systemctl enable piclock

# Disable auto-start on boot
sudo systemctl disable piclock

# View real-time logs
sudo journalctl -u piclock -f

# View recent logs
sudo journalctl -u piclock --since "1 hour ago"
```

### Uninstall Service

```bash
# Remove the service
sudo ./uninstall_service.sh
```
```

## Configuration

The application uses sensible defaults and doesn't require a configuration file:

- **GPIO Pins**: 12 and 13 for clock control
- **NTP Server**: time.nist.gov
- **Sync Interval**: 5 minutes
- **Web Interface**: Port 5000 on all interfaces

To modify these settings, edit the values in `piclock.py`:

```python
# GPIO Configuration
self.tick_pin1 = 12
self.tick_pin2 = 13

# NTP Configuration
self.ntp_server = "time.nist.gov"
self.ntp_sync_interval = 300  # 5 minutes

# Flask Configuration
self.flask_host = "0.0.0.0"
self.flask_port = 5000
```

## Advanced Pulsing Configuration

The application includes sophisticated pulsing logic for optimal clock control:

### Normal Ticking Parameters
- `norm_tick_ms`: Length of forward tick pulse (31ms default)
- `norm_tick_on_us`: Duty cycle of forward tick pulse (60μs out of 100μs)

### Fast-Forward Parameters
- `fwd_tick_ms`: Length of fast-forward tick pulse (32ms default)
- `fwd_tick_on_us`: Duty cycle of fast-forward tick pulse (60μs)
- `fwd_count_mask`: Speed control (1 = 4 ticks/sec default)
- `fwd_speedup`: Speed multiplier (4x default)

### Reverse Parameters (Region-Specific)
**Region A (seconds 35-55):**
- `rev_ticka_t1_ms`: Short pulse length (10ms)
- `rev_ticka_t2_ms`: Delay before long pulse (7ms)
- `rev_ticka_t3_ms`: Long pulse length (28ms)
- `rev_ticka_on_us`: Duty cycle (90μs)

**Region B (other seconds):**
- `rev_tickb_t1_ms`: Short pulse length (10ms)
- `rev_tickb_t2_ms`: Delay before long pulse (7ms)
- `rev_tickb_t3_ms`: Long pulse length (28ms)
- `rev_tickb_on_us`: Duty cycle (82μs)

### Synchronization Thresholds
- `diff_threshold_ss`: Seconds tolerance (30s default)
- `diff_threshold_mm`: Minutes threshold (0 default)
- `diff_threshold_hh`: Hours threshold (6 default)

These parameters can be configured via the API or by editing the values in `piclock.py`.

## Usage

### Web Interface

Access the web interface at `http://your-pi-ip:5000`

- **Dashboard**: Real-time clock status and time synchronization
- **Configuration**: Set clock time and NTP settings
- **Controls**: Pause/resume clock operation

### API Endpoints

- `GET /api/current_time` - Get current RTC time
- `GET /api/clock_time` - Get current clock position
- `POST /api/set_clock_time` - Set clock time
- `GET /api/clock_status` - Get clock operation status
- `POST /api/pause_clock` - Pause clock
- `POST /api/resume_clock` - Resume clock
- `GET /api/pulsing_config` - Get pulsing configuration
- `POST /api/pulsing_config` - Update pulsing configuration

### Running the Application

```bash
# Run directly
python3 piclock.py

# Run in background
nohup python3 piclock.py > piclock.log 2>&1 &

# Run with screen
screen -S piclock
python3 piclock.py
# Press Ctrl+A, then D to detach
```

## Security Considerations

### Production Deployment

1. **Network Security**:
   - Use a reverse proxy (nginx) for HTTPS
   - Configure firewall rules
   - Limit access to trusted networks

2. **Application Security**:
   - Run as dedicated user if needed
   - Validate all input parameters
   - Proper error handling

3. **Hardware Security**:
   - Review and restrict GPIO permissions
   - Monitor system logs
   - Regular security updates

### Security Checklist

- [ ] Change default web interface port
- [ ] Configure firewall rules
- [ ] Set up HTTPS with reverse proxy
- [ ] Review and restrict GPIO permissions
- [ ] Monitor system logs
- [ ] Regular security updates

## Troubleshooting

### Common Issues

1. **GPIO Permission Errors**:
   ```bash
   sudo usermod -a -G gpio $USER
   sudo chmod 666 /dev/gpiomem
   ```

2. **I2C Not Detected**:
   ```bash
   sudo raspi-config  # Enable I2C
   sudo i2cdetect -y 1
   ```

3. **Import Errors**:
   ```bash
   pip3 install -r requirements.txt
   ```

4. **NTP Sync Issues**:
   - Check internet connectivity
   - Verify NTP server availability
   - Review firewall settings

### Debug Mode

For development/testing, run with verbose logging:

```bash
python3 piclock.py
```

### Log Analysis

```bash
# View application logs
tail -f piclock.log

# Check system logs
dmesg | grep -i i2c
dmesg | grep -i gpio
```

## Development

### Project Structure

```
piclock/
├── piclock.py          # Main application
├── requirements.txt    # Python dependencies
├── templates/         # HTML templates
│   ├── index.html
│   └── config.html
└── static/           # Static assets
    ├── style.css
    └── scripts.js
```

### Building from Source

```bash
# Install development dependencies
pip3 install -r requirements.txt

# Run tests (if available)
python3 -m pytest

# Run application
python3 piclock.py
```

## Performance Optimization

### Production Optimizations

1. **Resource Management**: Efficient memory usage
2. **Efficient Polling**: Optimized API calls and caching
3. **Thread Safety**: Proper synchronization mechanisms
4. **Error Handling**: Graceful degradation and recovery

### Monitoring

```bash
# Monitor resource usage
htop
iotop
nethogs

# Check application health
ps aux | grep piclock
netstat -tlnp | grep 5000
```

## Deployment

### Quick Start

1. Clone the repository
2. Install dependencies: `pip3 install -r requirements.txt`
3. Run: `python3 piclock.py`
4. Access web interface at `http://your-pi-ip:5000`

### Production Deployment

1. Copy files to target directory
2. Install dependencies: `pip3 install -r requirements.txt`
3. Set up process manager (systemd, supervisor, etc.)
4. Configure firewall and security
5. Start application

### Process Management

For production use, consider using a process manager:

```bash
# Using systemd (create service file)
sudo systemctl start piclock

# Using supervisor
supervisorctl start piclock

# Using screen
screen -S piclock -d -m python3 piclock.py
```

## License

This project is based on the work of victor-chew's espclock project. All credit for research goes to him.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
- Check the troubleshooting section
- Review application logs
- Open an issue on GitHub
- Check the original espclock documentation
