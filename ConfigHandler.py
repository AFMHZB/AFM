from tkinter import filedialog
import os

class ConfigHandler(object):
    def __init__(self):
        self.config_dict = {}
        
    def read_from_file(self, path):
        with open(path, 'r') as afile:
            lines = [[line[1:-1]] if '[' in line else line.split('=') for line in afile.read().splitlines()]
            for line in lines:
                if len(line) == 1:
                    section = line[0]
                    self.config_dict[section] = {}
                elif len(line) >= 2:
                    key = line[0]
                    val = line[1]
                    if ';' in val:
                        values = [x for x in val.split(';')]
                    else:
                        try:
                            values = float(val)
                        except ValueError:
                            values = val
                    self.config_dict[section][key] = values
        return self.config_dict
    
    def write_to_file(self, path, adict):
        with open(path, 'w') as afile:
            for sec in adict.keys():
                afile.write('[' + sec + ']\n')
                for key in adict[sec].keys():
                    afile.write(key + '=' + str(adict[sec][key]) + '\n')
            
    def path_dialog_save(self):
        name = filedialog.asksaveasfilename(filetypes=(('Config Files', '*.ini'), ("All Files", "*.*")))
        return name
        
    def path_dialog_read(self):
        name = filedialog.askopenfilename(filetypes=(("Config Files","*.ini"), ("All Files", "*.*")))
        return name
    
    def path_dialog_dir(self):
        name = filedialog.askdirectory(initialdir=os.getcwd(), title='Please select a destination for the HDF5 Files')
        return name
