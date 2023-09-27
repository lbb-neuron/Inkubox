import numpy as np
import threading
import time

import RPi.GPIO as GPIO

class Temp_Controller:
	def __init__(self,is_values,ought_values):
		self.is_values     = is_values
		self.ought_values  = ought_values
		
		self.inkugo = False # This is set for the polystyrene inkugo only
		if self.inkugo:
			self.kp            = 0.10000
			self.ki            = 0.00020
			self.kd            = 7.5
		else:
			self.kp            = 0.30000
			self.ki            = 0.00500
			self.kd            = 0.0
		self.dt            = 1
		
		self.cp           = 0.0
		self.ci           = 0.0
		
		GPIO.setmode(GPIO.BCM)
		
		GPIO.setup(20,GPIO.OUT)
		GPIO.setup(21,GPIO.OUT)
		GPIO.setup(16,GPIO.OUT)
		GPIO.output(16,GPIO.LOW)

		self.pwm1 = GPIO.PWM(20,4000)
		self.pwm2 = GPIO.PWM(21,4000)
		self.pwm1.start(0)
		self.pwm2.start(0)
		
		self.old_temp = self.is_values['temperature'].value
		self.t_d      = time.time()
		
		self.current_mode = -1 # This variable is used to remeber mode and update ci if mode changes so that controller does not have drastic over/undershoots when mode is changed
		
		self.thr          = threading.Thread(target=self.run,args=())
		self.thr.start()
				
	def run(self):
		time.sleep(3)
		t                 = time.time() + self.dt
		
		while True:
			# Always calculate the d part of the controller
			new_temp      = self.is_values['temperature'].value
			new_t_d       = time.time()
			d_part        = (new_temp-self.old_temp)/(new_t_d-self.t_d+0.01)
			self.old_temp = new_temp
			self.t_d      = new_t_d
			self.cd       = np.clip(-d_part * self.kd,-0.1,0.1)
			
			if self.is_values['status'].value < 0.5:
				self.control_temp(True,0)
			else:
				if abs(self.current_mode - self.is_values['mode'].value) > 0.5:
					# Mode has changed. Reset ci
					self.current_mode = self.is_values['mode'].value
					if self.current_mode > 0.5:
						# Heating
						self.ci = 0.7
					else:
						# Cooling
						self.ci = -0.5
				
				error         = self.ought_values['temperature'].value - self.is_values['temperature'].value
				
				self.cp       = self.kp * error
				
				if not self.inkugo:
					self.ci       = self.ki * error * self.dt + self.ci
					self.ci       = max(min(self.ci,1.0),-1.0) # Bounding ci to minimize initial overshoot
				
					# If abs(error) > 2, then do maximum heating (through ci) and make sure that ci get resetted next cycle (through self.current_mode)
					if error > 2:
						if self.current_mode > 0.5: # This means we want to heat
							self.ci = 10
							self.current_mode = -1
					elif error < -2:
						if self.current_mode < 0.5: # This means we want to cool
							self.ci = -10
							self.current_mode = -1
				
					c             = self.cp + self.ci + self.cd
				else:
					# Controller for polystyrene box
					if error > 5:
						if self.current_mode > 0.5:
							c = 10
							self.ci = 0.1
						else:
							c = 0
							self.ci = 0
					elif error < -5:
						if self.current_mode < 0.5:
							c = -10
							self.ci = -10
						else:
							c = 0
							self.ci = 0
					else:
						self.ci       = self.ki * error * self.dt + self.ci
						self.ci       = max(min(self.ci,2.0),-2.0)
						c             = self.cp + self.ci + self.cd
				
				print(self.is_values['mode'].value,self.is_values['temperature'].value,c,self.ci)
				if self.is_values['mode'].value < 0.5:
					self.control_temp(False,-c)
				else:
					self.control_temp(True,c)
				
			while time.time() < t:
				time.sleep(0.02)
			t += self.dt
			
	
	def control_temp(self,heating,c):
		if c <= 0:
			self.pwm1.ChangeDutyCycle(0)
			self.pwm2.ChangeDutyCycle(0)
			GPIO.output(16,GPIO.LOW)
		elif heating:
			# heating
			self.pwm2.ChangeDutyCycle(0)
			self.pwm1.ChangeDutyCycle(min(int(10*c),100))
			GPIO.output(16,GPIO.HIGH)
		else:
			# cooling
			self.pwm1.ChangeDutyCycle(0)
			self.pwm2.ChangeDutyCycle(min(int(50*c),100))
			GPIO.output(16,GPIO.HIGH)
		
