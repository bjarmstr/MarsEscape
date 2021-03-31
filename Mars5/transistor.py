# transistor
#instructables.com/Raspberry-Pi-GPIO-Circuits_controlling-High-power


import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)
GPIO.setup(4,GPIO.OUT)
while True:
    GPIO.output(4,True)
    print("True")
    time.sleep(2)
    GPIO.output(4, False)
    print("off")
    time.sleep(1)
    