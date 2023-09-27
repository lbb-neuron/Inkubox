import time

import threading

class Temp:
	def __init__(self, queue, is_values):
		self.queue     = queue
		self.is_values = is_values
		
		self.thr = threading.Thread(target=self.run,args=())
		self.thr.start()
		
	def run(self):
		while True:
			if self.queue.qsize() < 10:
				self.queue.put(['measure','temperature_start'])
				time.sleep(0.5)
				self.queue.put(['measure','temperature_read'])
			else:
				print('Queue is overloaded (temp.py)')
			time.sleep(0.5)
			
