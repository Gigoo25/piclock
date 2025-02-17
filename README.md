# PiClock - Drive an analog clock using a Raspberry Pi, RTC & NTP

A simple Python script that can drive the internal mechanism of an analog ticking clock. This will not work with 'silent' analog clocks without heavy modifications, as the 'silent' variations of quartz-driven clocks do not 'tick' once a second but rather constantly 'tick' to complete a revolution in 60 seconds.

This project is largely based on the work of victor-chew, which can be found [here](https://github.com/victor-chew/espclock), and his blog, which can be found [here](https://www.randseq.org/search/label/espclock). All credit for research goes to him.

## Bill of Materials

- A Raspberry Pi (I am using a Raspberry Pi 3b+ even though it is way overkill).
- A modified ticking [clock mechanism](https://www.randseq.org/2016/10/hacking-analog-clock-to-sync-with-ntp_29.html).
- A DS3231 RTC module.
- Dupont wires.
- Adafruit I2C Non-Volatile FRAM Breakout (Coming soon).

## Features

- Accurate timekeeping.
- Clock can forward tick, reverse tick, pulse in place & fast forward.
- Clock is able to be daemonized and started on boot (Coming soon).
- Flask web interface to control the clock remotely (Coming soon).
- FRAM Breakout module to be able to recover from power outages (Coming soon).

## Installation

PiClock requires [Python](https://www.python.org/) v3.11+ to run.

Run the script and provide it with an accurate timestamp on the analog clock.

```sh
pip3 install -r requirements.txt
python3 piclock.py