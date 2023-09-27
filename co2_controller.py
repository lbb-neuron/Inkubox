import numpy as np
import time

import threading

import RPi.GPIO as GPIO

class Co2_Controller:
	def __init__(self, is_values, ought_values):
		self.is_values           = is_values
		self.ought_values        = ought_values
				
		self.on_interval         = np.array([0.05, 0.1,  0.1, 0.1, 0.2])
		self.off_min_interval    = np.array([1,  1,    0.75,  0.5,   0.5])
		self.margin_error        = np.array([0,   0.05, 0.2, 0.7, 2])
		
		self.time_last_injection = 0
		
		self.pin_valve           = 18
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(self.pin_valve,GPIO.OUT)
		GPIO.output(self.pin_valve,GPIO.LOW)
				
		self.thr = threading.Thread(target=self.run,args=())
		self.thr.start()
	
	def run(self):
		time.sleep(3)
		
		while(True):
			if self.is_values['co2_status'].value < 0.1:
				time.sleep(0.1)
				continue
			
			error = self.ought_values['co2'].value - self.is_values['co2'].value
			while error <= 0:
				time.sleep(0.1)
				error = self.ought_values['co2'].value - self.is_values['co2'].value
							
			index = int(np.sum((self.margin_error<=error)*1.) - 0.5)
			
			self.open_valve()
			time.sleep(self.on_interval[index])
			self.close_valve()
			time.sleep(self.off_min_interval[index])
			self.time_last_injection = time.time()
	
	def open_valve(self):
		GPIO.output(self.pin_valve,GPIO.HIGH)
		
	def close_valve(self):
		GPIO.output(self.pin_valve,GPIO.LOW)
