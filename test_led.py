#!/usr/bin/env python3
"""
LED GPIO Test
  GPIO 26 : LED 1
  GPIO 16 : LED 2
"""

import time
import RPi.GPIO as GPIO

LED1 = 26
LED2 = 19

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(LED1, GPIO.OUT)
GPIO.setup(LED2, GPIO.OUT)

def all_off():
    GPIO.output(LED1, GPIO.LOW)
    GPIO.output(LED2, GPIO.LOW)

print("LED GPIO Test  |  GPIO26=LED1  GPIO16=LED2")
print("按 Ctrl+C 停止\n")

try:
    # 1. 開機確認：兩顆同時亮 1 秒
    print("[1] 兩顆 LED 全亮...")
    GPIO.output(LED1, GPIO.HIGH)
    GPIO.output(LED2, GPIO.HIGH)
    time.sleep(1)
    all_off()
    time.sleep(0.3)

    # 2. 輪流閃爍（各亮 0.5 秒，跑 5 輪）
    print("[2] 輪流閃爍 5 輪...")
    for i in range(5):
        print(f"    輪次 {i+1}：LED1 HIGH, LED2 LOW")
        GPIO.output(LED1, GPIO.HIGH)
        GPIO.output(LED2, GPIO.LOW)
        time.sleep(0.5)
        print(f"    輪次 {i+1}：LED1 LOW,  LED2 HIGH")
        GPIO.output(LED1, GPIO.LOW)
        GPIO.output(LED2, GPIO.HIGH)
        time.sleep(0.5)
    all_off()
    time.sleep(0.3)

    # 3. 同步閃爍（兩顆同時，跑 5 次）
    print("[3] 同步閃爍 5 次...")
    for i in range(5):
        GPIO.output(LED1, GPIO.HIGH)
        GPIO.output(LED2, GPIO.HIGH)
        time.sleep(0.3)
        GPIO.output(LED1, GPIO.LOW)
        GPIO.output(LED2, GPIO.LOW)
        time.sleep(0.3)

    print("\n測試完成，所有 LED 已關閉。")

except KeyboardInterrupt:
    print("\n使用者中斷測試。")

finally:
    all_off()
    GPIO.cleanup()
    print("GPIO cleaned up.")
