# coding: utf8
__version__ = '0.1'

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.utils import platform
from kivy.logger import Logger
from kivy.uix.popup import Popup
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
#Avoid keyboard to hide text input
from kivy.core.window import Window
Window.softinput_mode = 'below_target'

from jnius import autoclass

from oscpy.client import OSCClient
from oscpy.server import OSCThreadServer
from struct import unpack

from arduinoBLE import ArduinoBLE
import numpy as np

from pathlib import Path
from android.storage import primary_external_storage_path
from datetime import datetime
#from geopy import Nominatim

SERVICE_NAME = u'{packagename}.Service{servicename}'.format(
    packagename=u'ch.unil.issul.issulab',
    servicename=u'Kitelogger'
)
class MyPopup(Popup):
    pass

class KiteApp(App):
    recording = False
    gps_address = StringProperty("")
    gps_lat = NumericProperty(None)
    gps_lon = NumericProperty(None)
    gps_accuracy = NumericProperty(None)

    F_front = NumericProperty(None)
    F_back = NumericProperty(None)
    board_battery = NumericProperty(None)
    board_connected = StringProperty("")

    board = None
    board_upload = False
    
    def build(self):
        
        #Start service with application
        self.service = None
        self.start_service()

        #define osc server to communicate with service
        self.server = OSCThreadServer()
        self.server.listen(address=b'localhost',port=3002,default=True,)
        #bind message to callback
        self.server.bind(b'/update_status',self.received_update)
        self.server.bind(b'/update_gps',self.received_gps_update)
        #define osc client to send message to service
        self.client = OSCClient(b'localhost', 3000)

        #Request update from service every 300 ms
        Clock.schedule_interval(self.request_update,0.3)
        Clock.schedule_interval(self.update_board,0.3)

        #Start board BLE object
        #self.board = ArduinoBLE("3a:3a:3a:ab:dc:C7",64*3+1)
        self.board = ArduinoBLE("19:91:0F:64:90:A6",64*2+1)

        #recording path
        gps_path = board_path = harness_path = None

        self.popup = MyPopup()
 
    def start_service(self):
        if platform == 'android':
            service = autoclass(SERVICE_NAME)
            self.mActivity = autoclass(u'org.kivy.android.PythonActivity').mActivity
            argument = ''
            service.start(self.mActivity, argument)
            self.service = service
        else:
            raise NotImplementedError(
                "service start not implemented on this platform"
            )

    def stop_service(self):
        if self.service:
            if platform == "android":
                self.service.stop(self.mActivity)
            else:
            	raise NotImplementedError(
                	"service start not implemented on this platform"
            	)
            self.service = None

    def update_board(self,_):
        data = np.asarray(self.board.data)
        if data.size >1 :
            #if len(data) >1 : self.rate = int((len(data)-1)*1000000/(data[-1][0]-data[0][0]))
            front = data[:,1:4]
            back = data[:,4:7]
            #compute mean values over received packet and sum 3 forces
            self.F_front = int(np.sum(np.mean(front,axis=0)))
            self.F_back = int(np.sum(np.mean(back,axis=0)))

        if self.board.battery :
            self.board_battery = self.board.battery
        
        if self.board.connected :
            self.board_connected = "connected"
            if self.board.connected_to_characteristic : 
                self.root.ids.record_btn.disabled = False   #device should be connected and subscribed to char to disable the record button
        else :
            self.board_connected = "connection lost"
            self.root.ids.record_btn.disabled = True
            self.board_battery = -1
            self.F_front = -1
            self.F_back = -1
        
        if (not self.board_upload) and self.board.upload :
            self.popup.open()
            self.board_upload = True
        if self.board_upload and (not self.board.upload) :
            self.popup.dismiss()
            self.board_upload = False
        
        if self.board.arduino_filename :
            info = open(self.info_path,"a+") #open info file in append mode, create if doesn't exists.
            info.write("arduino board file : "+self.board.arduino_filename)
            info.close()
            self.board.arduino_filename = None


    def tare_board(self,value):
        #multiplier factor, tare is averaged on xx measurement
        value *= 10
        self.board.writeTare(value)
        #self.client.send_message(b'/tare_board',value.to_bytes(1,'big'))

    def tare_harness(self,value):
        #multiplier factor, tare is averaged on xx measurement
        value *= 10
        #self.client.send_message(b'/tare_harness',value.to_bytes(1,'big'))

    def record(self,state):

        #send record signal to sd card
        if state == 'down' :
            #define path to log datta
            self.definePath()
            #Start logging on board SD card
            self.board.recordSD(1) 
        if state == 'normal' :
            #send stop uploading signal
            self.board.recordSD(0)

        #Start logging GPS data
        if self.gps_path :
            gps_path = str(self.gps_path)
        else :
            gps_path = ""

        self.client.send_message(b'/record',[gps_path.encode('utf8')])
    
    def definePath(self):
        #make a path with internal storage directory, create ISSUL-lab directory, get current time and create a directory
        now = datetime.now()
        rider = self.root.ids.rider_label.text
        directory = Path(primary_external_storage_path(),'ISSUL-lab',rider,now.strftime('%Y_%m_%d-%H:%M:%S'))
        if not directory.exists() :
            directory.mkdir(parents=True)
        Logger.info("Directory created %s",directory)
        self.info_path = directory/'info.txt'
        self.gps_path = directory/'gps.csv'
        self.board_path = directory/'board.csv'
        self.harness_path = directory/'harness.csv'

        #send path to board
        self.board.set_path(self.board_path)

    def request_update(self,_):
        #ask service to send update
        self.client.send_message(b'/request_update',[])

    def received_update(self,message):
        self.recording = bool(message)
        #Logger.info("App: update received, %d",message)

        if self.recording:
            self.root.ids.record_btn.state="down"
            self.root.ids.record_btn.text="Recording in progress ..."
        #    self.root.ids.record_btn.background_color=(1,0,0,1)
        else :
            self.root.ids.record_btn.state="normal"
            self.root.ids.record_btn.text="Record"
        #    self.root.ids.record_btn.background_color=(1,1,1,1)

    def received_gps_update(self,*message):
        #decoded = message.decode('utf8')
        [self.gps_lat,self.gps_lon,self.gps_accuracy] = unpack('3f',bytes(message))
        #location = self.locator.reverse(str(gps_lat)+','+str(gps_lon))
        #self.gps_address = location.address
    
    def get_gps_position(self,message):
        decoded = message.decode('utf8')
        Logger.info("App: update gps position received, %s",message.decode('utf8'))
        self.gps_position = decoded

if __name__ == '__main__':
    KiteApp().run()
