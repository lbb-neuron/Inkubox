import time

import os

import threading

class Logger:
    def __init__(self, dir_name, is_values, ought_values):
        self.dir_name     = dir_name
        self.is_values    = is_values
        self.ought_values = ought_values
        
        # Check if directory exists
        if not os.path.isdir(self.dir_name):
            print("The following is not a directory name:")
            print(dir_name)
            print("No data logging has been done")
        
        # Create current folder
        self.t0           = time.time()
        self.folder_name  = time.strftime('%Y%m%d_%H%M%S', time.localtime(time.time()))
        self.path         = os.path.join(self.dir_name,self.folder_name)
        os.mkdir(self.path)
        
        # Start data logging
        self.postfix = 0
        self.counter = 0
        self.thr     = threading.Thread(target=self.run,args=())
        self.thr.start()
        
    def run(self):
        self.current_file = "data_" + str(self.postfix).zfill(4) + ".log"
        while True:
            if self.counter == 1000:
                self.counter  = 0
                self.postfix += 1
                self.current_file = "data_" + str(self.postfix).zfill(4) + ".log"
            if self.counter == 0:
                f = open(os.path.join(self.path,self.current_file),"w")
            else:
                f = open(os.path.join(self.path,self.current_file),"a")
            f.write(str(time.time()))
            f.write(", ")
            f.write(str(time.time()-self.t0))
            f.write(", ")
            f.write(str(self.ought_values['co2'].value))
            f.write(", ")
            f.write(str(self.is_values['co2'].value))
            f.write(", ")
            f.write(str(self.ought_values['temperature'].value))
            f.write(", ")
            f.write(str(self.is_values['temperature'].value))
            f.write(", ")
            f.write(str(self.is_values['humidity'].value))
            f.write(", ")
            f.write(str(self.is_values['status'].value))
            f.write(", ")
            f.write(str(self.is_values['mode'].value))
            f.write(", ")
            f.write(str(self.is_values['co2_status'].value))
            f.write(", ")
            f.write(str(self.is_values['charge'].value))
            f.write(", ")
            f.write(str(self.is_values['voltage'].value))
            f.write(", ")
            f.write(str(self.is_values['current'].value))
            f.write("\n")
            f.close()
            self.counter += 1;
            time.sleep(10)
