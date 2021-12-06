#Class to manage BLE using able
from able import BluetoothDispatcher, GATT_SUCCESS
from kivy.clock import Clock
from kivy.logger import Logger
from plyer import storagepath
import struct
import csv

class ArduinoBLE(BluetoothDispatcher) :
    #log
    log_prefix = "arduinoBLE:"
    #device
    mac_address = None
    #define characteristics
    data_characteristic = None
    battery_characteristic = None
    tare_characteristic = None
    record_characteristic = None
    upload_characteristic = None
    #received values
    mtu = None
    data = None
    battery = None
    data_struct = struct.Struct('I6f9f')
    #record
    log_file = None
    arduino_filename = None
    #status
    onTare = False
    onRecord = False
    connected = False
    connected_to_characteristic = False
    upload = False

    def __init__(self,mac_address,mtu):
        #init parrent class
        super().__init__()
        #get device information
        self.mac_address = mac_address
        self.mtu = mtu
        #schedule connection
        Clock.schedule_once(self.connect,0)

    def reset(self) : 
        self.data = None
        self.battery = None
        self.onTare = False
        self.onRecord = False

    def connect(self,_):
        if self.mac_address :
            self.connect_by_device_address(self.mac_address)
        else:
            Logger.error(self.log_prefix+" MAC Adress not defined")

    def on_connection_state_change(self, status, state):       
        #if connexion is succesfull discover services
        if status == GATT_SUCCESS and state:
            self.connected = True
            Logger.info(self.log_prefix+" Connection succesfull")
            self.discover_services()
        #else close current connection and schedule connect
        else:
            self.connected = False
            self.connected_to_characteristic = False
            Logger.info(self.log_prefix+" Connection failed or lost, try to re-connect")
            #close connection
            self.close_gatt()
            #reset class attributes
            self.reset()
            #Schedule re-connection
            Clock.schedule_once(self.connect,-1)

    def on_services(self, status, services):
        #discover services
        if status == GATT_SUCCESS:
            #Request MTU change : size equals to data packet size * number of packet per communication
            self.request_mtu(self.mtu+3) #mtu + 3 bytes for ATT
            #Search characteristcs
            self.data_characteristic = services.search("3fd2a1ce-2f24-4c33-b28f-639775d9df43")
            self.tare_characteristic = services.search("743e6a48-03f8-4511-ab7a-6caa052ffdaf")
            self.battery_characteristic = services.search("2A19")
            self.record_characteristic = services.search("0d55dc41-33c6-4a43-888c-989f7911420f")
            self.upload_characteristic = services.search("fd0e2894-e3f2-11eb-ba80-0242ac130004")
            
            if self.data_characteristic and self.tare_characteristic and self.battery_characteristic and self.record_characteristic and self.upload_characteristic:
                self.connected_to_characteristic = True

            #Subscribe to notifications
            if self.data_characteristic : 
                self.enable_notifications(self.data_characteristic, enable=True, indication=False)
                Logger.info(self.log_prefix+" Subscribed to DATA notifications")
            if self.battery_characteristic : 
                self.enable_notifications(self.battery_characteristic, enable=True, indication=False)
                Logger.info(self.log_prefix+" Subscribed to BATTERY notifications")
            if self.upload_characteristic : 
                self.enable_notifications(self.upload_characteristic, enable=True, indication=False)
                Logger.info(self.log_prefix+" Subscribed to UPLOAD notifications")
    
    def on_error(self, msg) :
        Logger.info(self.log_prefix+" on error : %s",msg)

    def on_mtu_changed(self, mtu, status):
        if status == GATT_SUCCESS and mtu == (self.mtu+3):
            Logger.info(self.log_prefix+" MTU changed: mtu=%d, status=%d", mtu, status)
        else:
            Logger.error(self.log_prefix+" MTU not changed: mtu=%d, status=%d", mtu, status)
    
    def writeTare(self,iter):
        #if iter is 0 then offset is rest on board
        #if iter is > 0 then iter is number of averaged measurements per load cells to perform a tare operation
        if self.connected :
            Logger.info(self.log_prefix+" Write tare arg=%d",iter)
            self.write_characteristic(self.tare_characteristic, iter.to_bytes(1,'big'))
            self.onTare = True
            #data value not shown during tare
            self.data = None    

    def recordSD(self,status):
        if self.connected :
            Logger.info(self.log_prefix+" Record arg=%d",status)
            self.write_characteristic(self.record_characteristic, status.to_bytes(1,'big'))
    
    def set_path(self,path):
        Logger.info(self.log_prefix+" set_path command received, data will be downloaded to :%s",str(path))
        self.log_file = open(path, 'w', newline='')
        self.writer = csv.writer(self.log_file, dialect='excel')
        self.writer.writerow(['timestamp[us]','F1[N]','F2[N]','F3[N]','F4[N]','F5[N]','F6[N]','accX[m/s2]','accy[m/s2]','accZ[m/s2]','gyroX[degree/s]','gyroY[degree/s]','gyroZ[degree/s]','magX[uT]','magY[uT]','magZ[uT]'])
        self.onRecord = True

    #to do on write change ....
    def on_characteristic_write(self,characteristic,status):
        if status == GATT_SUCCESS :
            if characteristic.uuid.toString() == self.tare_characteristic.uuid.toString() :
                self.onTare = False
                Logger.info(self.log_prefix+" Tare done")

            if characteristic.uuid.toString() == self.record_characteristic.uuid.toString() :
                    Logger.info(self.log_prefix+" Record signal received")
        
        else :
            Logger.info(self.log_prefix+"  last write command FAILED")

    def on_characteristic_changed(self,characteristic):
        #read data characteristic
        if characteristic.uuid.toString() == self.data_characteristic.uuid.toString() :
            #get raw data
            data_raw = characteristic.getValue()
            self.data = []
            #unpack data line by line (one transmitted paquet contains several lines)
            for line in self.data_struct.iter_unpack(bytes(data_raw)) :
              self.data.append(line)
            #if self.onRecord :   
            #    self.writer.writerows(temp)

        #downloading file
        if characteristic.uuid.toString() == self.upload_characteristic.uuid.toString() :
            #convert received data to byte
            received_data = bytes(characteristic.getValue())
            #Logger.info(self.log_prefix+" Raw data length:"+str(len(received_data)) +" data : "+str(received_data))
            #extract status byte
            status_byte = received_data[0]
            #if status byte equal to 1 this is valid data frame
            if status_byte == 1: 
                #convert data and write data to csv
                temp = []
                for line in self.data_struct.iter_unpack(bytes(received_data[1:])) :
                    temp.append(line)
                self.writer.writerows(temp)
                if not self.upload : 
                    self.upload = True
            #if status byte equal to 0 last paquet received, close file
            if status_byte == 0 :
                self.onRecord = False
                self.log_file.close()
                Logger.info(self.log_prefix+" Data download completed")
                self.upload = False
            #received filename
            if status_byte == 2 :
                data = received_data[1:13]
                self.arduino_filename = data.decode('UTF-8')
                Logger.info(self.log_prefix+" Arduino filename received : " + self.arduino_filename)
                

        #read battery characteristic
        if characteristic.uuid.toString() == self.battery_characteristic.uuid.toString():
            #self.battery = bytes(characteristic.getValue())[0]
            self.battery = int.from_bytes(characteristic.getValue(),'big')
            Logger.info(self.log_prefix+" Battery level changed = %d%%",self.battery)