'p4a example service using oscpy to communicate with main application.'

from time import localtime, asctime, sleep
from kivy.logger import Logger
from oscpy.server import OSCThreadServer
from oscpy.client import OSCClient
from struct import pack

from pathlib import Path
from android.storage import primary_external_storage_path
from datetime import datetime

from gps import GPS
#from arduinoBLE import ArduinoBLE

CLIENT = OSCClient('localhost', 3002)

class Controler : 
    recording = False

    def __init__(self) :
        self.gps = GPS()
        #self.board = ArduinoBLE("3a:3a:3a:ab:dc:C7",68*3)

    def tare_board(self,value):
        'answer to tare board request'
        Logger.info("Tare Board: value=%d",value)
        #self.board.writeTare(value)

    def tare_harness(self,value):
        'answer to tare harness request'
        Logger.info("Tare Harness: value=%d",value)

    def record(self,message):
        'answer to record request'
        self.recording = not self.recording
        Logger.info("Record request received: status %s",self.recording)
        gps_path = message.decode('utf8')
        if self.recording :
            self.gps.start_recording(gps_path)
        else : 
            self.gps.stop_recording()

    def send_update(self,*_):
        'send record status to application'
        #CLIENT.send_message(b'/update',self.recording.to_bytes(1,'big'))
        bundle_data = []
        bundle_data.append((b'/update_status',self.recording.to_bytes(1,'big')))
        bundle_data.append((b'/update_gps',pack('3f',self.gps.location['lat'],self.gps.location['lon'],self.gps.location['accuracy'])))
        #bundle_date.append((b'/update_board',))
        #Logger.info("debug :"+str(type(self.gps.location)))

        CLIENT.send_bundle(bundle_data)

    def send_gps_location(self):
        CLIENT.send_message(b'/update_gps_position',[self.gps_location.encode('utf8')])

if __name__ == '__main__':
    
    #create Controller object
    obj = Controler()

    #define OSC server for communication
    server = OSCThreadServer()
    server.listen('localhost', port=3000, default=True)
    #bind callbacks
    server.bind(b'/tare_board', obj.tare_board)
    server.bind(b'/tare_harness', obj.tare_harness)
    server.bind(b'/record', obj.record)
    server.bind(b'/request_update',obj.send_update)

    
    while True:
        sleep(0.01)
        #obj.send_update()
