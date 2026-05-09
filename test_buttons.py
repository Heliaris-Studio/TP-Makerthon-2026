#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO

BUTTONS = {1: 5, 2: 16, 3: 12, 4: 25}

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for gpio in BUTTONS.values():
    GPIO.setup(gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("按鈕測試 | 按任意按鈕 | Ctrl+C 停止\n")

prev = {n: GPIO.HIGH for n in BUTTONS}

try:
    while True:
        for n, gpio in BUTTONS.items():
            state = GPIO.input(gpio)
            if state == GPIO.LOW and prev[n] == GPIO.HIGH:
                print(f"按鈕{n} (GPIO{gpio}) 按下")
            elif state == GPIO.HIGH and prev[n] == GPIO.LOW:
                print(f"按鈕{n} (GPIO{gpio}) 放開")
            prev[n] = state
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n停止。")
finally:
    GPIO.cleanup()
