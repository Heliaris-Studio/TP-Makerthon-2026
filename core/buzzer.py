import time
import RPi.GPIO as GPIO

BUZZER = 22

def _tone(pwm, freq, duration):
    pwm.ChangeFrequency(freq)
    pwm.ChangeDutyCycle(50)
    time.sleep(duration)
    pwm.ChangeDutyCycle(0)
    time.sleep(0.05)

def play_waiting():
    """外送員按鈕：等燈音效（短三聲）"""
    pwm = GPIO.PWM(BUZZER, 1000)
    pwm.start(0)
    for _ in range(2):
        _tone(pwm, 920, 0.2)
    pwm.stop()
    del pwm

def play_victory():
    """學生開箱：勝利5音"""
    pwm = GPIO.PWM(BUZZER, 1000)
    pwm.start(0)
    notes = [523, 659, 784, 1047, 1319]  # C5 E5 G5 C6 E6
    for freq in notes:
        _tone(pwm, freq, 0.15)
    pwm.stop()
    del pwm
