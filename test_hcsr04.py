#!/usr/bin/env python3
"""
HC-SR04 Ultrasonic Sensor Test
  Trig : GPIO 17
  Echo : GPIO 27
"""

import time
import RPi.GPIO as GPIO

TRIG = 17
ECHO = 27

TIMEOUT_S = 0.02          # 20 ms — good for up to ~3 m
SPEED_OF_SOUND = 34300    # cm/s at ~20 °C


def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)
    GPIO.output(TRIG, GPIO.LOW)
    time.sleep(0.5)        # let sensor settle


def measure_distance() -> float | None:
    """
    Send a 10 µs pulse on TRIG and measure the ECHO pulse width.
    Returns distance in centimetres, or None on timeout.
    """
    # Trigger pulse
    GPIO.output(TRIG, GPIO.HIGH)
    time.sleep(0.00001)    # 10 µs
    GPIO.output(TRIG, GPIO.LOW)

    deadline = time.time() + TIMEOUT_S

    # Wait for ECHO to go HIGH
    while GPIO.input(ECHO) == GPIO.LOW:
        if time.time() > deadline:
            print("[WARN] Timeout waiting for ECHO HIGH — check wiring")
            return None
    pulse_start = time.time()

    deadline = pulse_start + TIMEOUT_S

    # Wait for ECHO to go LOW
    while GPIO.input(ECHO) == GPIO.HIGH:
        if time.time() > deadline:
            print("[WARN] Timeout waiting for ECHO LOW — object too close or wiring issue")
            return None
    pulse_end = time.time()

    duration = pulse_end - pulse_start
    distance = (duration * SPEED_OF_SOUND) / 2
    return distance


def main():
    setup()
    print(f"HC-SR04 Test  |  TRIG=GPIO{TRIG}  ECHO=GPIO{ECHO}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            dist = measure_distance()
            if dist is not None:
                print(f"Distance: {dist:7.2f} cm")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    finally:
        GPIO.cleanup()
        print("GPIO cleaned up.")


if __name__ == "__main__":
    main()
