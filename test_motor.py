#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO

SERVO = 13

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(SERVO, GPIO.OUT)

pwm = GPIO.PWM(SERVO, 50)  # SG90 需要 50Hz
pwm.start(0)

def set_angle(angle):
    duty = 2.5 + (angle / 180.0) * 10.0  # 2.5% = 0°, 12.5% = 180°
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)  # 停止訊號避免抖動

try:
    print("移到 0°")
    set_angle(0)
    time.sleep(1)

    print("移到 90°（中間）")
    set_angle(90)
    time.sleep(1)
    
    print("移到 180°（中間）")
    set_angle(180)
    time.sleep(1)
    
    set_angle(0)

except KeyboardInterrupt:
    print("\n使用者中斷。")
finally:
    pwm.stop()
    del pwm
    GPIO.cleanup()
    print("GPIO cleaned up.")

