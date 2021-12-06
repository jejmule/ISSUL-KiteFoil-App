from plyer import gps
from kivy.logger import Logger
import csv
from numpy import nan
import time

PRE = " GPS :"

class GPS :
    location = {'lat':nan,'lon':nan,'accuracy':nan}
    #lat = lon = speed = bearing = altitude = accuracy = None
    record = False

    def __init__(self) :
        try:
            gps.configure(on_location=self.on_location, on_status=self.on_status)
        
        except NotImplementedError:
            import traceback
            traceback.print_exc()
            self.gps_status = 'GPS is not implemented for your platform'
        
        self.start(1,0.1)
        self.file = None
    
    def __del__(self) :
        self.stop()
        if self.file :
            self.file.close()

    
    def start(self,minTime_ms=100,minDist_m=0.1) :
        Logger.info(PRE+" Start GPS : min time %s ms, min distance %s m", minTime_ms, minDist_m)
        gps.start(minTime_ms,minDist_m)

    def stop(self):
        Logger.info(PRE+" Stop GPS ")
        gps.stop()

    def start_recording(self,path):
        Logger.info(PRE+" Start recording : %s", path)
        self.file = open(path,'w', newline='')
        fieldnames = ['time','lat', 'lon','altitude','speed','bearing','accuracy']
        self.writer = csv.DictWriter(self.file, fieldnames=fieldnames)
        self.writer.writeheader()
        #write current location
        self.writer.writerow(self.location)
        self.record = True
    
    def stop_recording(self):
        Logger.info(PRE+" Stop recording ")
        self.record = False
        self.file.close()

    def on_location(self,**kwargs):
        #copy location
        self.location = dict(kwargs)
        #get time from epoch as string
        self.location['time'] = time.time()
        #record
        if self.record :
            self.writer.writerow(self.location)

    def on_status(self, stype, status):
        gps_status = 'type={}\t{}'.format(stype, status)
        Logger.info(PRE+" Status : %s",gps_status)