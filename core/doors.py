import time
import threading
import RPi.GPIO as GPIO
import core.config as cfg
from core.buzzer import play_waiting, play_victory

_servo_l = None
_servo_r = None


def init(servo_l, servo_r):
    global _servo_l, _servo_r
    _servo_l, _servo_r = servo_l, servo_r


def _set_servo(pwm_obj, angle):
    pwm_obj.ChangeDutyCycle(2.5 + (angle / 180.0) * 10.0)
    time.sleep(0.6)
    pwm_obj.ChangeDutyCycle(0)


def _set_leds(side, green_on: bool):
    if side == "left":
        GPIO.output(cfg.LED_L_GREEN, GPIO.HIGH if green_on else GPIO.LOW)
        GPIO.output(cfg.LED_L_RED,   GPIO.LOW  if green_on else GPIO.HIGH)
        cfg.state["led_l_green"] = green_on
        cfg.state["led_l_red"]   = not green_on
    else:
        GPIO.output(cfg.LED_R_GREEN, GPIO.HIGH if green_on else GPIO.LOW)
        GPIO.output(cfg.LED_R_RED,   GPIO.LOW  if green_on else GPIO.HIGH)
        cfg.state["led_r_green"] = green_on
        cfg.state["led_r_red"]   = not green_on


def set_led(side, green_on: bool):
    _set_leds(side, green_on)


def open_door(side, buzzer_mode="delivery"):
    if not cfg.door_lock.acquire(blocking=False):
        return   # 另一扇門正在動作中，忽略重複觸發
    try:
        threading.Thread(target=(play_waiting if buzzer_mode == "delivery" else play_victory), daemon=True).start()
        if side == "left":
            cfg.state["door_left"] = "open"
            _set_leds("left", True)
            _set_servo(_servo_l, 85)
            time.sleep(5)
            _set_servo(_servo_l, 0)
            _set_leds("left", False)
            cfg.state["door_left"] = "closed"
        else:
            cfg.state["door_right"] = "open"
            _set_leds("right", True)
            _set_servo(_servo_r, 85)
            time.sleep(5)
            _set_servo(_servo_r, 0)
            _set_leds("right", False)
            cfg.state["door_right"] = "closed"
    finally:
        cfg.door_lock.release()

