import logging
import time

import RPi.GPIO as GPIO


class Clock:
    def __init__(
        self,
        hour_hand_position: int,
        minute_hand_position: int,
        second_hand_position: int,
        tick_pin1: int,
        tick_pin2: int,
    ) -> None:
        self.hour_hand_position: int = hour_hand_position
        self.minute_hand_position: int = minute_hand_position
        self.second_hand_position: int = second_hand_position

        self.tick_pin1: int = tick_pin1
        self.tick_pin2: int = tick_pin2

        self.paused: bool = False
        self.fast_forward: bool = False
        self.reverse: bool = False
        self.current_tick_pin: int = self.tick_pin1

    def send_pulse(self, pin, duration, next_tick_delay=0) -> None:
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(next_tick_delay)

    def forward_tick(self) -> None:
        self.reverse = False
        self.send_pulse(self.current_tick_pin, 0.1)
        self.current_tick_pin = (
            self.tick_pin2
            if self.current_tick_pin == self.tick_pin1
            else self.tick_pin1
        )
        self.update_clock_position()

    def reverse_tick(self) -> None:
        self.reverse = True
        self.send_pulse(self.current_tick_pin, 0.01)
        self.current_tick_pin = (
            self.tick_pin1
            if self.current_tick_pin == self.tick_pin2
            else self.tick_pin2
        )
        self.send_pulse(self.current_tick_pin, 0.03)
        self.update_clock_position()

    def synchronize_clock(
        self, rtc_hour: int, rtc_minute: int, rtc_second: int
    ) -> tuple[int, int, int]:
        total_seconds_diff: int = self.calculate_time_difference(
            rtc_hour, rtc_minute, rtc_second
        )

        logging.info(f"RTC time: {rtc_hour:02}:{rtc_minute:02}:{rtc_second:02}")
        logging.info(
            f"Clock time: {self.hour_hand_position:02}:{self.minute_hand_position:02}:{self.second_hand_position:02}"
        )

        if rtc_hour is not None:
            tolerance = 1

            if abs(total_seconds_diff) <= tolerance:
                self.fast_forward = False
                self.forward_tick()
            elif total_seconds_diff > tolerance:
                logging.info(
                    f"Clock is behind RTC time by {total_seconds_diff} seconds"
                )
                self.fast_forward = True
                self.forward_tick()
            else:
                logging.info(
                    f"Clock is ahead of RTC time by {abs(total_seconds_diff)} seconds"
                )
                self.fast_forward = False
                self.reverse_tick()

        return (
            self.hour_hand_position,
            self.minute_hand_position,
            self.second_hand_position,
        )

    def calculate_time_difference(self, hour: int, minute: int, second: int) -> int:
        if self.hour_hand_position == 12:
            clock_hour_24 = 0 if hour < 12 else 12
        else:
            clock_hour_24: int = self.hour_hand_position
            if hour >= 12:
                clock_hour_24 += 12

        ntp_total_seconds = hour * 3600 + minute * 60 + second
        clock_total_seconds = (
            clock_hour_24 * 3600
            + self.minute_hand_position * 60
            + self.second_hand_position
        )

        total_seconds_diff = ntp_total_seconds - clock_total_seconds

        if total_seconds_diff > 21600:
            total_seconds_diff -= 43200
        elif total_seconds_diff < -21600:
            total_seconds_diff += 43200

        return total_seconds_diff

    def update_clock_position(self) -> None:
        if self.reverse:
            self.second_hand_position = (self.second_hand_position - 1) % 60
            if self.second_hand_position == 59:
                self.minute_hand_position = (self.minute_hand_position - 1) % 60
                if self.minute_hand_position == 59:
                    self.hour_hand_position = (self.hour_hand_position - 1) % 12
        else:
            self.second_hand_position = (self.second_hand_position + 1) % 60
            if self.second_hand_position == 0:
                self.minute_hand_position = (self.minute_hand_position + 1) % 60
                if self.minute_hand_position == 0:
                    self.hour_hand_position = (self.hour_hand_position + 1) % 12
