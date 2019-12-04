import sys
import clr
import time
import cv2
import numpy as np
import ctypes
import os
import epics
import System
import h5py
import configparser as cfg
import matplotlib.pyplot as plt
from System import Array, Int32
from System.Runtime.InteropServices import GCHandle, GCHandleType
from datetime import datetime
from NeaSNOMConnect import NeaSNOMConnect
from Find_Bact import *


_MAP_NET_NP = {
    'Single' : np.dtype('float32'),
    'Double' : np.dtype('float64'),
    'SByte'  : np.dtype('int8'),
    'Int16'  : np.dtype('int16'),
    'Int32'  : np.dtype('int32'),
    'Int64'  : np.dtype('int64'),
    'Byte'   : np.dtype('uint8'),
    'UInt16' : np.dtype('uint16'),
    'UInt32' : np.dtype('uint32'),
    'UInt64' : np.dtype('uint64'),
    'Boolean': np.dtype('bool'),
}

def asNumpyArray(netArray):
    '''
    Given a CLR `System.Array` returns a `numpy.ndarray`.  See _MAP_NET_NP for
    the mapping of CLR types to Numpy dtypes.
    '''
    dims = np.empty(netArray.Rank, dtype=int)
    for I in range(netArray.Rank):
        dims[I] = netArray.GetLength(I)
    netType = netArray.GetType().GetElementType().Name

    try:
        npArray = np.empty(dims, order='C', dtype=_MAP_NET_NP[netType])
    except KeyError:
        raise NotImplementedError("asNumpyArray does not yet support System type {}".format(netType) )

    try: # Memmove
        sourceHandle = GCHandle.Alloc(netArray, GCHandleType.Pinned)
        sourcePtr = sourceHandle.AddrOfPinnedObject().ToInt64()
        destPtr = npArray.__array_interface__['data'][0]
        ctypes.memmove(destPtr, sourcePtr, npArray.nbytes)
    finally:
        if sourceHandle.IsAllocated: sourceHandle.Free()
    return npArray

class ScanAbortException(Exception):
    pass

class Scan:
    def __init__(self, scan_dict):
        self.OBSERVER_LABEL = ['live_afm', 'bact', 'points', 'progress', 'hide_plot', 'afm', 'live_plot', 'plot']
        self.exit = False
        self.observers = {}
        for label in self.OBSERVER_LABEL:
            self.observers[label] = []
        self.progress = 0
        self.preview_size = (400, 400)
        self.avrg_pointer = 0
        self.hdf5_dict = {}
        self.hdf5_path = os.getcwd()
        self.hdf5_dict['Data'] = {}
        self.hdf5_dict['Info'] = scan_dict['Info']
        self.hdf5_dict['Info']['AFM'] = scan_dict['AFM']
        self.hdf5_dict['Info']['Fourier'] = scan_dict['Fourier']
        self.channel = []
        for key in scan_dict['Channel'].keys():
            if scan_dict['Channel'][key] == 1:
                self.channel.append(key.upper())
        self.hdf5_dict['Info']['Channel'] = self.channel
        self.hdf5_dict['Info']['Characteristics'] = scan_dict['Characteristics']
        self.hdf5_dict['Info']['Measurement'] = scan_dict['Measurement']
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type == 'abort':
            #try:
            with h5py.File(self.hdf5_path, 'w') as hdf:
                self.dict_to_hdf5(hdf, self.hdf5_dict)
            #except OSError:
                #print('OSError')
        try:
            self.neaConnect.__exit__(exc_type, exc_val, exc_tb)
        except AttributeError:
            pass
        return
    
    def set_afm_channel(self, channel):
        try:
            self.neaConnect.set_afm_channel(channel)
        except AttributeError:
            pass
        
    def set_plot_channel(self, channel):
        try:
            self.neaConnect.set_plot_channel(channel)
        except AttributeError:
            pass
    
    def bind_to(self, name, callback):
        self.observers[name].append(callback)
    
    def dict_to_hdf5(self, group, adict):
        for key, value in adict.items():
            if isinstance(value, dict):
                next_group = group.create_group(key)
                self.dict_to_hdf5(next_group, value)
            else:
                try:
                    group.create_dataset(key, data=np.atleast_1d(value))
                except TypeError:
                    #special type for strings
                    group.create_dataset(key, data=np.array(value, dtype=h5py.special_dtype(vlen=bytes)))
                    
    def pause(self):
        try:
            self.neaConnect.pause()
        except AttributeError:
            print('No Measurement running.')
    
    def resume(self):
        try:
            self.neaConnect.resume()
        except AttributeError:
            print('No Measurement running.')
            
    def abort(self):
        try:
            self.neaConnect.abort()
        except AttributeError:
            print('No Measurement running.')
    
    def is_completed(self):
        try:
            return self.neaConnect.is_completed()
        except AttributeError:
            return True

    def is_started(self):
        try:
            return self.neaConnect.is_started()
        except AttributeError:
            return False
        
    def set_plot(self, raw):            
        for callback in self.observers['live_plot']:
            callback(raw)
    
    def set_wait_for_injection(self, boolean):
        self.neaConnect.set_wait_for_injection(boolean)
        
    def set_progress(self, progress):
        self.progress = progress
        for callback in self.observers['progress']:
            callback(progress)
            
    def set_live_image(self, data):
        #np.nan_to_num(x)
        cur_data = asNumpyArray(data)
        live_image = cv2.normalize(cur_data, None,0,255,cv2.NORM_MINMAX, cv2.CV_8U)
        live_image = cv2.resize(live_image, self.preview_size)
        for callback in self.observers['live_afm']:
            callback('live_afm', live_image)
            
    def set_bact_image(self, image):
        bact_image = cv2.resize(image, self.preview_size)
        for callback in self.observers['bact']:
            callback('bact', bact_image)
    
    def set_cur_image(self, image):
        cur_image = cv2.resize(image, self.preview_size)
        for callback in self.observers['points']:
            callback('points', cur_image)
    
    def set_afm_image(self, data):
        image = cv2.normalize(data, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
        image = cv2.resize(image, self.preview_size)
        for callback in self.observers['afm']:
            callback('afm', image)
        
    def set_plot_image(self, data):
        for callback in self.observers['plot']:
            callback('plot', data)
    
    def scan_setup(self, step):
        #self.set_live_image(np.zeros(self.preview_size))
        self.set_bact_image(np.zeros(self.preview_size))
        self.set_cur_image(np.zeros(self.preview_size))
        now = datetime.now().strftime('%Y-%m-%d %H%M')
        self.hdf5_dict['Info']['datetime'] = now
        os.makedirs(self.hdf5_dict['Info']['Measurement']['dest_path'], exist_ok = True)
        all_shorts = []
        operators = self.hdf5_dict['Info']['operators']
        operators = operators if isinstance(operators, list) else [operators]
        for op in operators:
            shorts = ''
            for name in op.split():
                shorts += name[0].upper()
            all_shorts.append(shorts)
        
        ops = '_'.join(all_shorts)
        
        if self.hdf5_dict['Info']['AFM']['dx'] == self.hdf5_dict['Info']['AFM']['dy']:
            scanarea = str(self.hdf5_dict['Info']['AFM']['dx'])
        else:
            scanarea = '{}x{}'.format(self.hdf5_dict['Info']['AFM']['dx'], self.hdf5_dict['Info']['AFM']['dy'])
            
        if self.hdf5_dict['Info']['AFM']['px'] == self.hdf5_dict['Info']['AFM']['py']:
            pixelarea = str(self.hdf5_dict['Info']['AFM']['px'])
        else:
            pixelarea = '{}x{}'.format(self.hdf5_dict['Info']['AFM']['px'], self.hdf5_dict['Info']['AFM']['py'])

        scan_name = '{} {}_{}_{}µm_{}px_{}of{}'.format(now, ops, self.hdf5_dict['Info']['project'], int(scanarea), int(pixelarea), int(step), int(self.hdf5_dict['Info']['Measurement']['iterations']))
        self.hdf5_path = os.path.join(self.hdf5_dict['Info']['Measurement']['dest_path'], scan_name + '.hdf5')
            
    def afm_scan(self):
        self.neaConnect = NeaSNOMConnect('192.168.89.44', os.path.join(os.getcwd(), 'updates/SDK/'), con_needed = True)
        self.neaConnect.bind_to('Progress', self.set_progress)
        self.neaConnect.bind_to('Cur_Data', self.set_live_image)
        
        self.hdf5_dict['Info']['Version'] = {}
        self.hdf5_dict['Info']['Version']['Client'] = self.neaConnect.client_version()
        self.hdf5_dict['Info']['Version']['Server'] = self.neaConnect.server_version()
        afm_data = self.neaConnect.scanAFM(**self.hdf5_dict['Info']['AFM'], channel_names = self.channel)
        print('Übersichtsscan ist fertig')
        if not afm_data == {}:
            data_path = os.path.join(self.hdf5_dict['Info']['Measurement']['dest_path'], self.hdf5_dict['Info']['datetime'] + '_CSV')
            os.makedirs(data_path, exist_ok = True)
            for k in afm_data.keys():
                afm_data[k] = asNumpyArray(afm_data[k])
                np.savetxt(os.path.join(data_path, k + '.csv'), afm_data[k], delimiter=',')
        return afm_data
    
    def compressed_scan(self):
        self.scan_setup()
        for x in range(5):
            afm_data = self.afm_scan()
            ratio = self.hdf5_dict['Info']['AFM']['dx'] / self.hdf5_dict['Info']['AFM']['px'] #um / px
            f = FindBacteria(self.hdf5_dict['Info']['Characteristics'], ratio)
            data = f.full_correction(afm_data['Z'], afm_data['R-Z'], self.hdf5_dict['Info']['AFM']['hlimit'] * 10**(-6))
            contours = f.find_all_contours(data)
            new_center = f.get_center(contours)
            if old_center:
                drift_x = new_center[0] - old_center[0]
                drift_y = new_center[1] - old_center[1]
                print('Drift: ', (drift_x, drift_y))
                self.hdf5_dict['Info']['AFM']['x0'] += drift_x
                self.hdf5_dict['Info']['AFM']['y0'] += drift_y
            old_center = new_center
            time.sleep(60)
        
        
                    
    def full_scan(self, step, csv_path=''):
        try:
            self.scan_setup(step)
            new_meas = (csv_path == '')
                
            if new_meas:
                afm_data = self.afm_scan()
            else:
                afm_data = {}
                for root, dirs, files in os.walk(csv_path):
                    for f in files:
                        c = f.split('.')[0]
                        afm_data[c] = np.loadtxt(os.path.join(root, f), delimiter=',')
                
            if 'Z' in afm_data.keys() and 'R-Z' in afm_data.keys():
                self.set_afm_image(afm_data['Z'])
                ratio = self.hdf5_dict['Info']['AFM']['dx'] / self.hdf5_dict['Info']['AFM']['px'] #um / px
                f = FindBacteria(self.hdf5_dict['Info']['Characteristics'], ratio)
                data = f.full_correction(afm_data['Z'], afm_data['R-Z'], self.hdf5_dict['Info']['AFM']['hlimit'] * 10**(-6))
                bac_found = f.find_bacteria(data, self.hdf5_dict['Info']['AFM']['hlimit'] * 10**(-6))
                bact_dict = f.get_dict()
                self.set_bact_image(bact_dict['Bacteria_IMG'])
                if bac_found:
                    for key in bact_dict['Bacteria'].keys():
                        #get the absolute coords for the relative points
                        for k in bact_dict['Bacteria'][key]['Points'].keys():
                            newx = ((bact_dict['Bacteria'][key]['Points'][k]['Coord'][0] * ratio) - (self.hdf5_dict['Info']['AFM']['dx'] / 2)) + self.hdf5_dict['Info']['AFM']['x0']
                            newy = ((bact_dict['Bacteria'][key]['Points'][k]['Coord'][1] * ratio) - (self.hdf5_dict['Info']['AFM']['dy'] / 2)) + self.hdf5_dict['Info']['AFM']['y0']
                            newx = round(newx, 2)
                            newy = round(newy, 2)
                            bact_dict['Bacteria'][key]['Points'][k]['Coord'] = (newx, newy)
                            
                        if new_meas:
                            (x0, y0) = bact_dict['Bacteria'][key]['Points']['Center']['Coord']
                            dxy = bact_dict['Bacteria'][key]['dxy']
                            res = bact_dict['Bacteria'][key]['pxy']
                            
                            self.set_cur_image(bact_dict['Bacteria'][key]['Meassurement_Points_IMG'])
                            
                            ##hier neu starten
                            
                            while not self.neaConnect.get_meas_completed():
                                spec_data = self.neaConnect.scanAFM(x0, y0, dxy, dxy, res, res, 0, self.hdf5_dict['Info']['AFM']['t_int'], self.hdf5_dict['Info']['AFM']['setpoint'],
                                                            self.hdf5_dict['Info']['AFM']['hlimit'], channel_names = self.channel)
                                
                                bact_dict['Bacteria'][key]['AFM'] = {}
                                for k in spec_data.keys():
                                    spec_data[k] = asNumpyArray(spec_data[k])
                                    bact_dict['Bacteria'][key]['AFM'][k] = spec_data[k]
                                
                                data = f.full_correction(spec_data['Z'], spec_data['R-Z'], self.hdf5_dict['Info']['AFM']['hlimit'] * 10**(-6))
                                bac_still_there = f.find_bacteria(data, self.hdf5_dict['Info']['AFM']['hlimit'] * 10**(-6))
                                small_bact_dict = f.get_dict()
                                
                                if bac_still_there:
                                    for k in small_bact_dict['Bacteria']['Bacteria1']['Points'].keys():
                                        newx = ((small_bact_dict['Bacteria']['Bacteria1']['Points'][k]['Coord'][0] * ratio) - (dxy / 2)) + x0
                                        newy = ((small_bact_dict['Bacteria']['Bacteria1']['Points'][k]['Coord'][1] * ratio) - (dxy / 2)) + y0
                                        bact_dict['Bacteria'][key]['Points'][k]['Coord'] = (newx, newy)
                                    
                                            
                                    for k in bact_dict['Bacteria'][key]['Points'].keys():
                                        #x0, y0, dx, dy, x_res, y_res, angle, t_int, offset, distance, averaging, resolution, source, channel_names
                                        self.neaConnect.bind_to('Fourier', self.set_plot)
                                        bact_dict['Bacteria'][key]['Points'][k]['Current'] = epics.caget('CUM1ZK3RP:rdCur')
                                        print(k)
                                        
                                        fourier_data = self.neaConnect.scan_fourier(bact_dict['Bacteria'][key]['Points'][k]['Coord'][0], bact_dict['Bacteria'][key]['Points'][k]['Coord'][1], 0, 0,
                                                                                **self.hdf5_dict['Info']['Fourier'], channel_names = self.channel)
                                        if self.neaConnect.get_wait_for_injection():
                                            print('Unterbrochen wegen Epics')
                                            break
                                        
                                        for fk in fourier_data.keys():
                                            fourier_data[fk] = asNumpyArray(fourier_data[fk])
                                            bact_dict['Bacteria'][key]['Points'][k][fk] = fourier_data[fk]
                                            
                                else:
                                    print('Bacteria could not be identified. Drift seems to be too strong')

                                while self.neaConnect.get_wait_for_injection():
                                    time.sleep(0.5)
                                        
                        else:
                            self.set_cur_image(bact_dict['Bacteria'][key]['Meassurement_Points_IMG'])
                
                self.hdf5_dict['Data'] = bact_dict
            
            else:
                print('Z and/or R-Z is not in Channel, therefore can not proceed.')

            self.hdf5_dict['Data']['AFM'] = afm_data
        except ScanAbortException:
            return
        
    
    def test_fourier(self):
        self.set_bact_image(np.zeros(self.preview_size))
        self.set_cur_image(np.zeros(self.preview_size))
        for callback in self.observers['hide_plot']:
            callback('show_plot')
        self.neaConnect = NeaSNOMConnect('192.168.89.44', os.path.join(os.getcwd(), 'updates/SDK/'), con_needed = True)
        self.neaConnect.bind_to('Fourier', self.set_plot)
        while not self.neaConnect.get_meas_completed():
            while self.neaConnect.get_wait_for_injection():
                time.sleep(0.5)
            if not self.neaConnect.get_meas_completed():
                fourier_data = self.neaConnect.scan_fourier(52.002673267326735, 49.87623762376238, 0, 0, 1, 1, 0, 20, 510, 800, 2, 700, 'Synchrotron', ['Z', 'O1A', 'O2A'])
