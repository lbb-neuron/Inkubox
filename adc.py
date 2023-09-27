import time

import threading

import numpy as np

class ADC:
    def __init__(self, queue, is_values):
        self.queue     = queue
        self.is_values = is_values
        
        self.t0        = time.time()
        for i in range(5):
            self.queue.put(['measure','adc'])
            time.sleep(1)
        
        self.thr = threading.Thread(target=self.run,args=())
        self.thr.start()
        
    def run(self):
        while True:
            if self.queue.qsize() < 10:
                self.queue.put(['measure','adc'])
            else:
                print('Queue is overloaded (adc.py)')
                
            # Sleep for 2 sec
            time.sleep(2)
            
            # Load values from
            try:
                saved_data = np.load('battery_state.npy')
            except:
                print('Could not recover old battery state')
                saved_data = np.array([0.0,0.0,0.0])
            # [0] .. maximal charge [technically energy not a charge]
            # [1] .. charge consumed so far [technically energy not a charge]
            # [2] .. battery voltage
            
            # Load charge from 
            if self.is_values['charge'].value < 0:
                self.is_values['charge'].value = saved_data[1]
                
            # Update time
            t1      = time.time()
            dt      = t1 - self.t0
            self.t0 = t1
            
            # Update saved_data vector
            self.is_values['charge'].value = self.is_values['charge'].value + dt * self.is_values['voltage'].value * self.is_values['current'].value
            saved_data[1] = self.is_values['charge'].value
            saved_data[2] = self.is_values['voltage'].value
            
            # Update the maximal charge value, if the voltage is too low
            # TODO
            
            # Save data in file
            np.save('battery_state.npy',saved_data)

                
