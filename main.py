from curtsies import Input

import co2 as CO2
import co2_controller

import temp as Temp
import temp_controller

import adc as ADC

import multiprocessing as mp
import threading

import i2c as I2C

import logger

import numpy as np

import time

import RPi.GPIO as GPIO

def check_for_key_press(key_presses):
    with Input(keynames='curses') as input_generator:
        for e in input_generator:
            if e == 'o': # On/OFF
                print("o")
                key_presses.value = 1.0
            elif e == 'm': # Mode: Heat/cool
                print("m")
                key_presses.value = 2.0
            elif e == 'c': # Toggle CO2
                print("c")
                key_presses.value = 3.0
            elif e == 's': # Calibrate co2
                print("s")
                key_presses.value = 4.0
            else:
                key_presses.value = 0.0

def main():
    ought_temp_hot  =  37
    ought_temp_cold =   4
    fan_hot_pwr     =  90
    fan_cold_pwr    = 100
    
    # Do not set is_values here. Instead, the are set in gui.py
    is_values    = {"temperature": mp.Value('d',0.0), 
                    "co2": mp.Value('d',0.0),
                    "humidity": mp.Value('d',0.0),
                    "voltage": mp.Value('d',0.0),
                    "current": mp.Value('d',0.0),
                    "charge": mp.Value('d',-1.0),
                    "status": mp.Value('d',0.0),
                    "mode": mp.Value('d',1.0),
                    "co2_status": mp.Value('d',0.0)}
    ought_values = {"temperature": mp.Value('d',ought_temp_hot), 
                    "co2": mp.Value('d',5.0)}
    
    key_presses  = mp.Value('d',0.0)
    
    # Starting thread to look at button presses
    thr = threading.Thread(target=check_for_key_press, args=(key_presses,))
    thr.start()
    print("Thread started")
    
    # Peltier ventilation
    pin_vent      = 17
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin_vent,GPIO.OUT)
    #GPIO.output(pin_vent,GPIO.LOW)
    pwm_fan = GPIO.PWM(pin_vent, 100)
    pwm_fan.start(0)

    # Setting all buttons as inputs
    btn_status = 5
    btn_co2    = 6
    btn_mode   = 19
    btn_lock   = 26

    GPIO.setup(btn_status,GPIO.IN)
    GPIO.setup(btn_co2,GPIO.IN)
    GPIO.setup(btn_mode,GPIO.IN)
    GPIO.setup(btn_lock,GPIO.IN)
    
    i2c       = I2C.I2c(is_values)
    co2       = CO2.Co2(i2c.queue,is_values)
    temp      = Temp.Temp(i2c.queue,is_values)
    adc       = ADC.ADC(i2c.queue,is_values)
    
    co2_ctrl  = co2_controller.Co2_Controller(is_values,ought_values)
    
    temp_ctrl = temp_controller.Temp_Controller(is_values,ought_values)
    
    dir_name  = "/home/inkugo2/log/"
    log       = logger.Logger(dir_name,is_values,ought_values)
    
    print("setup done")
    
    t0   = time.time()
    ctr  = 0 # This tells us for how long the button was pressed
    btns = 0 # This tells us which button was pressed
        
    while True:
        if time.time() - t0 > 3:
            i2c.queue.put(['display','update'])
            t0 += 3
            print(key_presses.value)
        if ctr == 0:
            # We are susceptible to button presses
            if GPIO.input(btn_lock):
                ctr = 0 # The lock is enabled and hence no button press is allowed
            elif GPIO.input(btn_status):
                ctr += 1
                btns = 0
                print("status")
            elif GPIO.input(btn_co2):
                ctr += 1
                btns = 1
                print("co2")
            elif GPIO.input(btn_mode):
                ctr += 1
                btns = 2
                print("mode")
            if key_presses.value > 0:
                print("Confirmed")
                if key_presses.value == 1.0:
                    btns = 0
                    ctr  = 5
                    print("Toogle ON/OFF")
                elif key_presses.value == 3.0:
                    btns = 1
                    ctr  = 5
                    print("Toogle ON/OFF CO2")
                elif key_presses.value == 2.0:
                    btns = 2
                    ctr  = 5
                    print("Toogle heat/cool mode")
                elif key_presses.value == 4.0:
                    btns = 1
                    ctr  = 500
                    print("Calibrate CO2")
                key_presses.value = 0.0
        else:
            if GPIO.input(btn_status) or GPIO.input(btn_co2) or GPIO.input(btn_mode):
                ctr += 1    # A button is still being  pressing a button
            else:
                if ctr < 5: # This means a button was not pressed long enough
                    ctr = 0
                else:
                    if btns == 0:
                        # Status button
                        is_values["status"].value = 1 - is_values["status"].value
                        if is_values["status"].value > 0.5:
                            if is_values["mode"].value > 0.5:
                                ought_values['temperature'].value = ought_temp_hot
                                pwm_fan.ChangeDutyCycle(fan_hot_pwr)
                            else:
                                ought_values['temperature'].value = ought_temp_cold
                                pwm_fan.ChangeDutyCycle(fan_cold_pwr)
                        else:
                            pwm_fan.ChangeDutyCycle(0)
                        i2c.queue.put(['display','update'])
                    elif btns == 1:
                        # CO2 button
                        if ctr > 250:
                            # Do a CO2 sensor calibration
                            i2c.queue.put(['calibrate','co2'])
                            i2c.queue.put(['display','co2_calibration'])
                            while i2c.queue.qsize() > 0:
                                pass
                            time.sleep(2)
                        else:
                            is_values["co2_status"].value = 1 - is_values["co2_status"].value
                        i2c.queue.put(['display','update'])
                    else:
                        # Mode button
                        is_values["mode"].value = 1 - is_values["mode"].value
                        if is_values["mode"].value > 0.5:
                            ought_values['temperature'].value = ought_temp_hot
                            if is_values["status"].value > 0.5:
                                pwm_fan.ChangeDutyCycle(fan_hot_pwr)
                        else:
                            ought_values['temperature'].value = ought_temp_cold
                            if is_values["status"].value > 0.5:
                                pwm_fan.ChangeDutyCycle(fan_cold_pwr)
                ctr  = 0
                btns = 0
        time.sleep(0.01)

if __name__ == '__main__':
    main()
