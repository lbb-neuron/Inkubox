import time

import threading

class Co2:
	def __init__(self, queue, is_values):
		self.queue     = queue
		self.is_values = is_values
		
		self.thr = threading.Thread(target=self.run,args=())
		self.thr.start()
		
	def run(self):
		while True:
			if self.queue.qsize() < 10:
				self.queue.put(['measure','co2_start'])
				time.sleep(0.25)
				self.queue.put(['measure','co2_read'])
			else:
				print('Queue is overloaded (co2.py)')
			time.sleep(0.75)
