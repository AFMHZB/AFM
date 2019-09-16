import sys
import clr
import time
import cv2
import numpy as np
import ctypes
import os
import System
import h5py
import configparser as cfg
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


class Scan:
    
    def __init__(self, scan_dict):
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
        with h5py.File(self.hdf5_path, 'w') as hdf:
            self.dict_to_hdf5(hdf, self.hdf5_dict)
        return
    
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
                    
    def start_scan(self, csv_path=''):
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

        scan_name = '{} {}_{}_{}µm_{}px'.format(now, ops, self.hdf5_dict['Info']['project'], scanarea, pixelarea)
        self.hdf5_path = os.path.join(self.hdf5_dict['Info']['Measurement']['dest_path'], scan_name + '.hdf5')
        
        new_meas = csv_path == ''
        
        with NeaSNOMConnect('192.168.89.44', os.path.join(os.getcwd(), 'updates/SDK/'), con_needed = new_meas) as neaConnect:
            
            if new_meas:
                self.hdf5_dict['Info']['Version'] = {}
                self.hdf5_dict['Info']['Version']['Client'] = neaConnect.client_version()
                self.hdf5_dict['Info']['Version']['Server'] = neaConnect.server_version()
                afm_data = neaConnect.scanAFM(**self.hdf5_dict['Info']['AFM'], channel_names = self.channel)
                data_path = os.path.join(self.hdf5_dict['Info']['Measurement']['dest_path'], now + '_CSV')
                os.makedirs(data_path, exist_ok = True)
                for k in afm_data.keys():
                    afm_data[k] = asNumpyArray(afm_data[k])
                    np.savetxt(os.path.join(data_path, k + '.csv'), afm_data[k], delimiter=',')
            else:
                afm_data = {}
                for root, dirs, files in os.walk(csv_path):
                    for f in files:
                        c = f.split('.')[0]
                        afm_data[c] = np.loadtxt(os.path.join(root, f), delimiter=',')
                        
                self.hdf5_dict['Data']['AFM'] = afm_data
                
            if 'Z' in afm_data.keys() and 'R-Z' in afm_data.keys():
                ratio = self.hdf5_dict['Info']['AFM']['dx'] / self.hdf5_dict['Info']['AFM']['px'] #um / px
                print(self.hdf5_dict['Info']['Characteristics'])
                f = FindBacteria(afm_data['Z'], afm_data['R-Z'], self.hdf5_dict['Info']['Characteristics'], ratio)
                data, top = f.data_correction(self.hdf5_dict['Info']['AFM']['hlimit'] * 10**(-6))
                bac_found = f.find_bacteria(data, top)
                bact_dict = f.get_dict()
                if bac_found:
                    for key in bact_dict['Bacteria'].keys():
                        #get the absolute coords for the relative points
                        for k in bact_dict['Bacteria'][key]['Points'].keys():
                            newx = ((bact_dict['Bacteria'][key]['Points'][k]['Coord'][0] * ratio) - (self.hdf5_dict['Info']['AFM']['dx'] / 2)) + self.hdf5_dict['Info']['AFM']['x0']
                            newy = ((bact_dict['Bacteria'][key]['Points'][k]['Coord'][1] * ratio) - (self.hdf5_dict['Info']['AFM']['dy'] / 2)) + self.hdf5_dict['Info']['AFM']['y0']
                            bact_dict['Bacteria'][key]['Points'][k]['Coord'] = (newx, newy)
                        
                        if new_meas:
                            (x0, y0) = bact_dict['Bacteria'][key]['Points']['Center']['Coord']
                            dxy = bact_dict['Bacteria'][key]['dxy']
                            res = bact_dict['Bacteria'][key]['pxy']

                            spec_data = neaConnect.scanAFM(x0, y0, dxy, dxy, res, res, 0, self.hdf5_dict['Info']['AFM']['t_int'], self.hdf5_dict['Info']['AFM']['setpoint'],
                                                        self.hdf5_dict['Info']['AFM']['hlimit'], channel_names = self.channel)
                            
                            bact_dict['Bacteria'][key]['AFM'] = {}
                            for k in spec_data.keys():
                                spec_data[k] = asNumpyArray(spec_data[k])
                                bact_dict['Bacteria'][key]['AFM'][k] = spec_data[k]
                            
                            for k in bact_dict['Bacteria'][key]['Points'].keys():
                                #x0, y0, dx, dy, x_res, y_res, angle, t_int, offset, distance, averaging, resolution, source, channel_names
                                fourier_data = neaConnect.scan_fourier(bact_dict['Bacteria'][key]['Points'][k]['Coord'][0], bact_dict['Bacteria'][key]['Points'][k]['Coord'][1], 0, 0,
                                                                        **self.hdf5_dict['Info']['Fourier'], channel_names = self.channel)
                                for fk in fourier_data.keys():
                                    fourier_data[fk] = asNumpyArray(fourier_data[fk])
                                    bact_dict['Bacteria'][key]['Points'][k][fk] = fourier_data[fk]
                            
                self.hdf5_dict['Data'] = bact_dict
            
            else:
                print('Z and/or R-Z is not in Channel, therefore can not proceed.')

            self.hdf5_dict['Data']['AFM'] = afm_data
