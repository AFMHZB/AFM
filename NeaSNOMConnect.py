import sys
import clr
import time

class NeaSNOMConnect:

    def __init__(self, ip, path='/home/sachse03/pc/Python/updates/SDK/', con_needed = True):
        if con_needed:
            self._progress = 0
            self._aborted = False
            self.afm_channel = 'Z'
            self.plot_channel = 'O2A'
            self._observers = {}
            self._observers['Progress'] = []
            self._observers['Cur_Data'] = []
            self._observers['Fourier'] = []
            self._ip = ip
            self._path = path
            self._wait_for_injection = False
            self._meas_completed = False
            ##### Import all DLLs in the folder
            sys.path.append(self._path)
            ##### Load the main DLL
            clr.AddReference('Nea.Client.Hardware')
            ##### Import the DLL as element neaSDK
            import Nea.Client.Hardware.SDK as neaSDK
            ##### Open up connection to microscope called neaClient
            self._neaClient = neaSDK.Connection(self._ip)
            ##### Define the Microscope neaMIC
            self._neaMic = self._neaClient.Connect()
            #remote = RPC.RpcHardware('nea-server-'+str(servernumber), 12982)
            ##### Short delay makes things working fine
            self._neaMic.CancelCurrentProcedure()
            self._neaMic.RegulatorOff()
            time.sleep(0.5)
            self._connected = True
        else:
            self._connected = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._connected:
            if exc_type == 'abort':
                self._aborted = True
            self._wait_for_injection = False
            self._meas_completed = True
            self.neaMic.CancelCurrentProcedure()
            self.neaMic.RegulatorOff()
            self.neaMic.Dispose()
            self.neaClient.Disconnect()
            self._connected = False

    @property
    def neaMic(self):
        return self._neaMic

    @property
    def neaClient(self):
        return self._neaClient
    
    def set_afm_channel(self, channel):
        self.afm_channel = channel
        
    def set_plot_channel(self, channel):
        self.plot_channel = channel
    
    def bind_to(self, name, callback):
        self._observers[name].append(callback)
    
    def pause(self):
        if self._scan:
            if not self._scan.IsSuspended:
                self._scan.Suspend()
                print('Suspend')
        else:
            print('Test')
    
    def resume(self):
        if self._scan:
            if self._scan.IsSuspended:
                self._scan.Resume()
                
    def get_progress(self):
        return self._scan.Progress
    
    def set_progress(self, progress):
        self._progress = progress
        for callback in self._observers['Progress']:
            callback(progress)
            
    def set_data(self, data):
        for callback in self._observers['Cur_Data']:
            callback(data)
            
    def set_fourier_data(self, data):
        for callback in self._observers['Fourier']:
            callback(data)
        
    def get_wait_for_injection(self):
        return self._wait_for_injection
    
    def set_wait_for_injection(self, boolean):
        self._wait_for_injection = boolean
    
    def get_meas_completed(self):
        return self._meas_completed
    
    def is_started(self):
        return self._scan.IsStarted

    def client_version(self):
        return self.neaMic.ClientVersion
    
    def get_channel(self, c):
        return self._data[c]

    def server_version(self):
        if self._connected:
            return self.neaMic.ServerVersion
        else:
            print('NeaSNOMConnect: Not Connected.')
            return None

    def in_contact(self):
        if self._connected:
            return self.neaMic.IsInContact
        else:
            print('NeaSNOMConnect: Not Connected.')
            return None

    def print_parameter(self, obj):
    #prints current microscope parameter
        params = [a for a in dir(obj) if not a.startswith('__') and not callable(getattr(obj,a))]
        for p in params:
            print(p + ': ' + str(getattr(obj, p)))

    #TODO: see if you can combine the scans (a lot of redundancy here)
    def scanAFM(self, x0, y0, dx, dy, px, py, angle, t_int, setpoint, hlimit, channel_names=['Z', 'R-Z']):
        if self._connected:
            if not self.in_contact():
                self.neaMic.AutoApproach(0.8)#80% setpoint
            self._scan = self.neaMic.PrepareAfmScan()
            self._scan.set_CenterX(x0)
            self._scan.set_CenterY(y0)
            self._scan.set_ScanAreaWidth(dx)
            self._scan.set_ScanAreaHeight(dy)
            self._scan.set_ResolutionColumns(px)
            self._scan.set_ResolutionRows(py)
            self._scan.set_ScanAngle(angle)
            self._scan.set_SamplingTime(t_int)
            #insert warning if too fast maybe
            self.print_parameter(self._scan)
            self._image = self._scan.Start()
            self._channel = {}
            for c in channel_names:
                self._channel[c] = self._image.GetChannel(c)
            print('Scanning..')
            while not self._scan.IsCompleted:
                self.set_progress(self._scan.Progress)
                self.set_data(self._channel[self.afm_channel].GetData())
                time.sleep(0.1)
            if self._aborted:
                return {}
            else:
                print('Done!')
                self._data = {}
                for c in self._channel.keys():
                    self._data[c] = self._channel[c].GetData()
                self.neaMic.RegulatorOff()
                time.sleep(0.5)
                return self._data

        else:
            print('NeaSNOMConnect: Not Connected.')
            return {}

    def scan_fourier(self, x0, y0, dx, dy, x_res, y_res, angle_f, t_int_f, offset, distance, averaging, resolution, source, channel_names):
        if self._connected:
            if not self.in_contact():
                self.neaMic.AutoApproach(0.8)
            self._scan = self.neaMic.PrepareFourierScan()
            self._scan.set_CenterX(x0)
            self._scan.set_CenterY(y0)
            self._scan.set_ScanAreaWidth(dx)
            self._scan.set_ScanAreaHeight(dy)
            self._scan.set_ResolutionColumns(x_res)
            self._scan.set_ResolutionRows(y_res)
            self._scan.set_ScanAngle(angle_f)
            self._scan.set_SamplingTime(t_int_f)
            self._scan.set_InterferometerOffset(offset)
            self._scan.set_InterferometerDistance(distance)
            self._scan.set_Averaging(averaging)
            self._scan.set_InterferogramResolution(resolution)
            self.print_parameter(self._scan)
            _image = self._scan.Start()
            _channel = {}
            for c in channel_names:
                _channel[c] = _image.GetChannel(c)
            print('Scanning..')
            while not self._scan.IsCompleted and not self._wait_for_injection:
                self.set_progress(self._scan.Progress)
                self.set_fourier_data(_channel[self.plot_channel].GetData())
                time.sleep(0.1)
            if self._scan.IsCompleted and not self._aborted:
                self._meas_completed = True
                _data = {}
                for c in _channel.keys():
                    _data[c] = _channel[c].GetData()
                self.neaMic.RegulatorOff()
                print('Done!')
                time.sleep(0.5)
                return _data
            else:
                self._scan.Cancel()
                self.neaMic.RegulatorOff()
                self._meas_completed = False
                return {}
        else:
            print('NeaSNOMConnect: Not Connected.')
            return {}
