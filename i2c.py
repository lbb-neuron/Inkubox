import smbus2 as smbus
import time

import numpy as np

import multiprocessing as mp
import threading

from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import busio

class I2c:
	def __init__(self, is_values):
		self.is_values = is_values
		
		self.i2c       = smbus.SMBus(1)
		
		self.co2_addr  = 0x29
		self.temp_addr = 0x70
		self.adc_addr  = 0x49
		self.disp_addr = 0x3C
		
		self.disp_update_ctr = 0
		
		self.queue     = mp.Queue()
		
		self.init()
		
		self.thr = threading.Thread(target=self.run,args=())
		self.thr.start()
	
	def init(self):
		self.display_init()
		self.co2_init()
		self.temp_init()
		self.adc_init()
		self.display_init_2()
		
	def destruct(self):
		self.co2_destruct()
		self.temp_destruct()
		self.adc_destruct()
		self.display_destruct()
	
	# CO2 sensor
	def co2_init(self):
		self.i2c.write_i2c_block_data(self.co2_addr,0x37,[0x68])            # Disable CRC
		self.i2c.write_i2c_block_data(self.co2_addr,0x36,[0x15,0x00,0x01])  # Choose CO2 in air (<100%)
		self.i2c.write_i2c_block_data(self.co2_addr,0x36,[0x24,0x7f,0xff])  # Set Humdity       (50 %)
		self.i2c.write_i2c_block_data(self.co2_addr,0x36,[0x1e,0x1c,0xe8])  # Set temperature   (37 degC)
		self.i2c.write_i2c_block_data(self.co2_addr,0x36,[0x2f,0x03,0xf5])  # Set pressure      (1013 mBar)
		self.i2c.write_i2c_block_data(self.co2_addr,0x3F,[0x6E])            # switch off autmatic calibration
		
		self.co2_value = 0.0
		
		self.co2_time  = time.time()
		
	def co2_destruct(self):
		pass # Soft reset was disabled. This is because it seems to cause issues when the CO2 sensor crashed
		# self.i2c.write_i2c_block_data(self.co2_addr,0x00,[0x06])            # Soft Reset
		
	def co2_measure_start(self):
		self.i2c.write_i2c_block_data(self.co2_addr,0x36,[0x39]) # Start measurement
		self.co2_time = time.time()
		
	def co2_measure_(self):
		data = smbus.i2c_msg.read(self.co2_addr,2) # 5 bit for hum
		self.i2c.i2c_rdwr(data)
		data = list(data)
		
		return 100*(data[0]*256.+data[1]-2**14)/2**15
				
	def co2_measure(self):
		while time.time() - 0.25 < self.co2_time:
			pass
		
		self.co2_value = self.co2_value*0.9+0.1*self.co2_measure_()
		
		self.is_values['co2'].value = self.co2_value
		
	def co2_calibrate(self):
		self.i2c.write_i2c_block_data(self.co2_addr,0x36,[0x61]) # Send forced calibration command (with 0 vol% CO2)
		self.co2_value              = 0
		self.is_values['co2'].value = 0 # Set value to 0
		
	# Temp sensor
	def temp_init(self):
		self.temp_value = 0.0
		self.hum_value  = 0.0
		time.sleep(0.25)
		self.i2c.write_i2c_block_data(self.temp_addr,0xB0,[0x98])
		time.sleep(0.25)
		self.i2c.write_i2c_block_data(self.temp_addr,0x35,[0x17])
		time.sleep(0.25)
		self.i2c.write_i2c_block_data(self.temp_addr,0x80,[0x5d])
		time.sleep(0.25)
		self.i2c.write_i2c_block_data(self.temp_addr,0x78,[0x66])
		
		self.temperature_time = time.time()
		
	def temp_destruct(self):
		pass
		
	def temp_measure_start(self):
		self.i2c.write_i2c_block_data(self.temp_addr,0x78,[0x66])
		self.temperature_time = time.time()
		
	def temp_measure_(self):
		while time.time() - 0.5 < self.temperature_time:
			pass
		
		data = smbus.i2c_msg.read(self.temp_addr,5) # 2 bit for temp only
		self.i2c.i2c_rdwr(data)
		data = list(data)
		
		if True:
			t_shtc3  = 175. * (data[0]*256+data[1])/65536.- 45
			rh_shtc3 = 100. * (data[3]*256+data[4])/65536. # Relative humidity is in percent here
			
			# Put humidity value into atomic memory
			self.hum_value = self.hum_value*0.75 + 0.26 * rh_shtc3
			self.is_values['humidity'].value = self.hum_value
			
			t_stc31  = t_shtc3  * 200
			rh_stc31 = int(rh_shtc3 * 65.535 + 0.5)
			
			self.i2c.write_i2c_block_data(self.co2_addr,0x36,[0x24,int(rh_stc31/256),int(rh_stc31%256)]) # Set Humdity
			self.i2c.write_i2c_block_data(self.co2_addr,0x36,[0x1e,int(t_stc31/256),int(t_stc31%256)])   # Set temperature
					
		return 175. * (data[0]*256+data[1])/65536.- 45
		
	def temp_measure(self):
		temp                                = self.temp_measure_()
		self.temp_value                     = self.temp_value*0.75 + 0.25*temp
		self.is_values['temperature'].value = self.temp_value
		
	# ADC board
	def adc_init(self):
		self.adc_switch_to_voltage()
		self.measure_voltage  = True
		self.time_last_switch = time.time()
		time.sleep(0.1)
		
		self.current_value = 0.0
		self.voltage_value = 0.0
				
	def adc_destruct(self):
		pass
		
	def adc_switch_to_current(self):
		self.i2c.write_i2c_block_data(self.adc_addr,0x01,[0xc0 | (1 << 4),0x83]) # Read from AIN1
		# AINP = AIN1, AINN = GND, FSR = 6.144V, Continuous mode, 
		# Data-rate: 128 SPS, Traditional comparator, 
		# comp-pol: active low, Latching comparator, disable comparator
		
	def adc_switch_to_voltage(self):
		self.i2c.write_i2c_block_data(self.adc_addr,0x01,[0xc0 | (0 << 4),0x83]) # Read from AIN0
		# AINP = AIN1, AINN = GND, FSR = 6.144V, Continuous mode, 
		# Data-rate: 128 SPS, Traditional comparator, 
		# comp-pol: active low, Latching comparator, disable comparator
		
	def adc_measure_current_(self):
		data = self.i2c.read_i2c_block_data(self.adc_addr,0x00,2)
		data = 256 * data[0] + data[1]
		if data >= 0x8000:
			data = 0 - (0x10000 - data)     # Number is negative. (2s complimant)
		voltage = data * 6.144 / (2. ** 15) # in V
		voltage = voltage / 5.              # scaling factor because of voltage divider and LM358. 
											# Important: Because of silicon bug in v2.1, this is not exact
		
		def f(x,a,b,c,d,e):
			return (((e*x + d)*x + c)*x + b)*x + a
		
		def v2i(v):
			return 10**f(v,-2.58880245,-2.81314991,30.0664798 ,-35.52758511,12.47022631) # fitted to data in datasheet
			
		return v2i(voltage) # Current in A0
		
	def adc_measure_voltage_(self):
		data = self.i2c.read_i2c_block_data(self.adc_addr,0x00,2)
		data = 256 * data[0] + data[1]
		if data >= 0x8000:
			data = 0 - (0x10000 - data) # Number is negative. (2s complimant)
		voltage = data * 6.144 / (2. ** 15)
		return voltage * 3 # Because of voltage divider
		
	def adc_measure(self):
		while self.time_last_switch + 0.25 > time.time():
			pass
			
		if self.measure_voltage:
			voltage = self.adc_measure_voltage_()
			self.voltage_value = voltage # self.voltage_value*0.9 + 0.1*voltage
			self.is_values['voltage'].value = self.voltage_value
			
			print("Voltage:",voltage)
			
			self.adc_switch_to_current()
			self.measure_voltage = False
		else:
			current = self.adc_measure_current_()
			self.current_value = current # self.current_value*0.9 + 0.1*current
			self.is_values['current'].value = self.current_value
			
			print("Current:",current)
			
			self.adc_switch_to_voltage()
			self.measure_voltage = True
			
		self.time_last_switch = time.time()

	# Display
	def display_init(self):
		self.disp       = adafruit_ssd1306.SSD1306_I2C(128,32,busio.I2C(3,2)) # 3 and 2 are the i2c GPIOs
		self.image      = Image.new("1",(128,32))
		self.draw       = ImageDraw.Draw(self.image)
		self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",10)
		self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",16)
		
		self.inkugo_0   = Image.fromarray(np.array(Image.open("./inkulogo/logo_0.bmp"))[:,:,0])
		
		# Switch display off
		self.draw.rectangle((0,0,128,32),fill=0) # Make everything black
		self.draw.bitmap((0,0),self.inkugo_0,fill=255)
		self.disp.image(self.image)
		self.disp.show()
		
		self.inkugo_1   = Image.fromarray(np.array(Image.open("./inkulogo/logo_1.bmp"))[:,:,0])
		self.inkugo_2   = Image.fromarray(np.array(Image.open("./inkulogo/logo_2.bmp"))[:,:,0])
		self.inkugo_3   = Image.fromarray(np.array(Image.open("./inkulogo/logo_3.bmp"))[:,:,0])


		# Sample images
		self.im_cool    = Image.fromarray(np.array(Image.open("./inkusigns/cool.bmp")))
		self.im_heat    = Image.fromarray(np.array(Image.open("./inkusigns/hot.bmp")))
		self.im_on      = Image.fromarray(np.array(Image.open("./inkusigns/on.bmp")))
		self.im_off     = Image.fromarray(np.array(Image.open("./inkusigns/off.bmp")))
		self.im_co2_on  = Image.fromarray(np.array(Image.open("./inkusigns/co2on.bmp")))
		self.im_co2_off = Image.fromarray(np.array(Image.open("./inkusigns/co2off.bmp")))
		
	def display_init_2(self):
		self.draw.rectangle((0,0,128,32),fill=0) # Make everything black
		self.draw.bitmap((0,0),self.inkugo_1,fill=255)
		self.disp.image(self.image)
		self.disp.show()

		self.draw.rectangle((0,0,128,32),fill=0) # Make everything black
		self.draw.bitmap((0,0),self.inkugo_2,fill=255)
		self.disp.image(self.image)
		self.disp.show()

		self.draw.rectangle((0,0,128,32),fill=0) # Make everything black
		self.draw.bitmap((0,0),self.inkugo_3,fill=255)
		self.disp.image(self.image)
		self.disp.show()
		
	def display_destruct(self):
		pass
		
	def display_co2_calibration(self):
		self.draw.rectangle((0,0,128,32),fill=0) # Make everything black
		self.draw.text((0,16),"CO2 calibrated",font=self.font_large,fill=255)

		self.disp.image(self.image)
		self.disp.show()

	def display_update(self,state):
		self.draw.rectangle((0,0,128,32),fill=0) # Make everything black

		self.draw.text((0,4),str(np.round(self.is_values['voltage'].value,1))+"V  "+str(int(1000*self.is_values['current'].value))+"mA",font=self.font_small,fill=255) # TODO: This is not implemented yet

		current_temp = int(self.is_values["temperature"].value*10)/10.
		current_co2  = int(self.is_values["co2"].value*10)/10.
		current_hum  = int(self.is_values["humidity"].value*10)/10.

		if state == 0:
			text = "Temp: " + str(current_temp) + " °C"
		elif state == 1:
			text = "CO2: " + str(current_co2) + " %"
		else:
			text = "Hum: " + str(current_hum) + " %"

		self.draw.text((0,16),text,font=self.font_large,fill=255)

		if self.is_values['status'].value < 0.5:
			self.draw.bitmap((71,0),self.im_off,fill=255)
		else:
			self.draw.bitmap((71,0),self.im_on,fill=255)

		if self.is_values['co2_status'].value < 0.5:
			self.draw.bitmap((91,0),self.im_co2_off,fill=255)
		else:
			self.draw.bitmap((91,0),self.im_co2_on,fill=255)

		if self.is_values['mode'].value < 0.5:
			self.draw.bitmap((111,0),self.im_cool,fill=255)
		else:
			self.draw.bitmap((111,0),self.im_heat,fill=255)

		self.disp.image(self.image)
		self.disp.show()


	
	def run(self):
		adc_error  = 0
		temp_error = 0
		co2_error  = 0
		try:
			while True:
				element = self.queue.get()
				if len(element) != 2:
					print('Command in queue is not usable',element)
					continue
				
				if element[0] == 'measure':
					if element[1] == 'temperature_read':
						# Measure temperature
						try:
							self.temp_measure()
							temp_error = 0
						except Exception as e:
							temp_error += 1
							print('Exception temperature read: ',temp_error)
							print(e)
							if temp_error > 5:
								temp_error = 0
								assert False # Restart i2c
					elif element[1] == 'temperature_start':
						# Measure temperature
						try:
							self.temp_measure_start()
							temp_error = 0
						except Exception as e:
							temp_error += 1
							print('Exception temperature start: ',temp_error)
							print(e)
							if temp_error > 5:
								temp_error = 0
								assert False # Restart i2c
					elif element[1] == 'co2_read':
						# Measure co2
						try:
							self.co2_measure_start()
							co2_error = 0
						except Exception as e:
							co2_error += 1
							print('Exception CO2 read: ',co2_error)
							print(e)
							if co2_error > 5:
								co2_error = 0
								assert False # Restart i2c
					elif element[1] == 'co2_start':
						# Measure co2
						try:
							self.co2_measure()
							co2_error = 0
						except Exception as e:
							co2_error += 1
							print('Exception CO2 start: ',co2_error)
							print(e)
							if co2_error > 5:
								co2_error = 0
								assert False # Restart i2c
					elif element[1] == 'adc':
						# Measure adc (current/voltage)
						# Measures current and voltage every other time
						# (i.e. each call measures either voltage
						# or the current)
						try:
							self.adc_measure()
							adc_error = 0
						except Exception as e:
							adc_error += 1
							print('Exception ADC: ',adc_error)
							print(e)
							if adc_error > 5:
								adc_error += 1
								assert False # Restart i2c
					else:
						print('Unknown sensor:',element[1])
				elif element[0] == 'calibrate':
					if element[1] == 'co2':
						self.co2_calibrate()
						time.sleep(0.25)
						print("CO2 is calibrated.")
					else:
						print('Unkown calibration command:',element[1])
				elif element[0] == 'display':
					if element[1] == 'update':
						self.display_update(self.disp_update_ctr)
						self.disp_update_ctr = (self.disp_update_ctr + 1) % 3
					elif element[1] == "co2_calibration":
						self.display_co2_calibration()
					else:
						print('Unknown display command:',element[1])
				else:
					print('Unknown command')
						
		except Exception as e:
			print('-------------------------------')
			print(e)
			print('-------------------------------')
			print('Close i2c port')
			self.i2c.close()
			time.sleep(1)
			print('Open i2c port')
			self.i2c = smbus.SMBus(1)
			time.sleep(1)
			print('Destruct i2c port')
			self.destruct()
			time.sleep(1)
			print('Init i2c port')
			self.init()
			
			print('Empty queue')
			while self.queue.qsize() > 0:
				self.queue.get()
			
			print('Restart i2c subroutine')
			self.run()
