import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import h5py as hdf5
from PIL import Image
from contextlib import redirect_stdout
import matplotlib.pyplot as plt
import io
import cv2
import numbers
import os
import copy
import configparser as cfg
import threading
import queue
from Scan import *

class StdoutRedirector(object):
    def __init__(self,text_widget, stream):
        self.text_space = text_widget
        self.stream = stream

    def write(self, string):
        self.text_space.insert('end', string)
        self.text_space.see('end')
        self.stream.flush()
        
    def writelines(self, strings):
        self.text_space.insert('end', strings)
        self.text_space.see('end')
        self.stream.flush()
    
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

def read_config(cfg_path):
    keys = ['Info', 'AFM', 'Fourier', 'Channel', 'Characteristics', 'Measurement']
    config = cfg.ConfigParser()
    config.read(cfg_path)
    config_flag = all(key in config.sections() for key in keys) and all(key in keys for key in config.sections())
    new_dict = {}
    for section in config.sections():
        new_dict[section] = {}
        for key, val in config.items(section):
            if ';' in val:
                values = []
                for x in val.split(';'):
                    try:
                        values.append(float(x))
                    except ValueError:
                        values.append(x)
                new_dict[section][key] = values
            else:
                try:
                    new_dict[section][key] = float(val)
                except ValueError:
                    new_dict[section][key] = val
    if not config_flag:
        raise ValueError('Wrong or Corrupted Config')
    return new_dict

class start_scan(tk.Tk):
    def __init__(self):
        self.scan = os.path.join(os.getcwd(), 'scan.ini')
        if not os.path.exists(self.scan):
            self.make_ini()
        self.scan_dict = read_config(self.scan)
        
        self.window = tk.Tk()
        self.window.title("Setup automatic FTIR-Spectroscopy")#
        self.message_queue = queue.Queue()
        self.message_event = '<<message>>'
        self.window.bind(self.message_event, self. process_message_queue)
        self.window['padx'] = 5
        self.window['pady'] = 5
        self.window.resizable(False, False)
        self.state = False
        self.window.bind("<F11>", self.toggle_fullscreen)
        self.window.bind("<Escape>", self.end_fullscreen)
        
        self.menu = tk.Menu(self.window)
        self.window.config(menu=self.menu)
        self.filemenu = tk.Menu(self.menu)
        self.menu.add_cascade(label="File", menu=self.filemenu)
        self.filemenu.add_command(label="Load Config", command=self.open_config)
        self.filemenu.add_command(label="Save Config", command=self.save_config)
        self.filemenu.add_command(label='Reset', command=self.fill_form)
        self.filemenu.add_separator()
        self.filemenu.add_command(label="Exit", command=self.window.destroy)
        
        style = ttk.Style()
        style.configure('TLabelframe', background='White')   
        style.configure('TLabelframe.Label', background='White')
        self.form_frame = ttk.LabelFrame(self.window, text="Measurement Setup", relief=tk.RIDGE)
        self.form_frame.pack(side=tk.TOP, fill=tk.BOTH, expand = tk.NO)
        
        self.entries = {}
        self.labels = {}
        
        #Info fields
        self.info_frame = ttk.LabelFrame(self.form_frame, text="Info", relief=tk.RIDGE)
        self.info_frame.pack(side=tk.TOP, fill = tk.BOTH, expand = tk.YES)
        tk.Grid.columnconfigure(self.info_frame, 1, weight=1)
        
        self.make_entry(self.info_frame, 0, 0, 'Project')
        self.make_entry(self.info_frame, 1, 0, 'Description')
        self.make_entry(self.info_frame, 2, 0, 'Operators')
        
        #AFM fields
        self.afm_frame = ttk.LabelFrame(self.form_frame, text="AFM", relief=tk.RIDGE)
        self.afm_frame.pack(side=tk.TOP, fill = tk.BOTH, expand = tk.YES)
        tk.Grid.columnconfigure(self.afm_frame, 2, weight=1)
        tk.Grid.columnconfigure(self.afm_frame, 4, weight=1)
        
        self.center_label = tk.Label(self.afm_frame, text='Center')
        self.center_label.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(self.afm_frame, 0, 1, 'X0')
        self.make_entry(self.afm_frame, 0, 3, 'Y0')
        
        self.area_label = tk.Label(self.afm_frame, text='Area')
        self.area_label.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(self.afm_frame, 1, 1, 'Dx')
        self.make_entry(self.afm_frame, 1, 3, 'Dy')
        
        self.res_label = tk.Label(self.afm_frame, text='Resolution')
        self.res_label.grid(row=2, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(self.afm_frame, 2, 1, 'Px')
        self.make_entry(self.afm_frame, 2, 3, 'Py')
        
        self.make_entry(self.afm_frame, 3, 1, 'Angle')
        self.make_entry(self.afm_frame, 3, 3, 'T_int')
        
        self.make_entry(self.afm_frame, 4, 1, 'Setpoint')
        self.make_entry(self.afm_frame, 4, 3, 'Hlimit')
        
        #Fourier fields
        self.fourier_frame = ttk.LabelFrame(self.form_frame, text="Fourier", relief=tk.RIDGE)
        self.fourier_frame.pack(side=tk.TOP, fill = tk.BOTH, expand = tk.YES)
        tk.Grid.columnconfigure(self.fourier_frame, 2, weight=1)
        tk.Grid.columnconfigure(self.fourier_frame, 4, weight=1)
        
        self.point_label = tk.Label(self.fourier_frame, text='Resolution')
        self.point_label.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(self.fourier_frame, 0, 1, 'X_res')
        self.make_entry(self.fourier_frame, 0, 3, 'Y_res')
        
        self.int_label = tk.Label(self.fourier_frame, text='Interferometer')
        self.int_label.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(self.fourier_frame, 1, 1, 'Offset')
        self.make_entry(self.fourier_frame, 1, 3, 'Distance')
        
        self.make_entry(self.fourier_frame, 2, 1, 'Averaging')
        self.make_entry(self.fourier_frame, 2, 3, 'Resolution')
        
        self.labels['Source'] = tk.Label(self.fourier_frame, text='Source')
        self.labels['Source'].grid(row=2, column=1, sticky=tk.N + tk.S + tk.E + tk.W)
        self.entries['Source'] = tk.Entry(self.fourier_frame)
        self.entries['Source'].grid(row=2, column=2, columnspan = 3, sticky=tk.N + tk.S + tk.E + tk.W)
        
        #Channel Fields
        self.channel_frame = ttk.LabelFrame(self.form_frame, text="Channel", relief=tk.RIDGE)
        self.channel_frame.pack(side=tk.TOP, fill = tk.BOTH, expand = tk.YES)
        for i in range(8):
            tk.Grid.columnconfigure(self.channel_frame, i, weight=1)
        
        channel = ['Z', 'M0A', 'M1A', 'M2A', 'M3A', 'M4A', 'M5A', 'M0P', 'M1P', 'M2P', 'M3P', 'M4P', 'M5P',
                  'O0A', 'O1A', 'O2A', 'O3A', 'O4A', 'O5A', 'O0P', 'O1P', 'O2P', 'O3P', 'O4P', 'O5P', 'M']
        self.checkbutton = {}
        self.check_var = {}
        x = 0
        for c in channel:
            rc = 'R-'+c
            self.check_var[c] = tk.IntVar()
            self.check_var[rc] = tk.IntVar()
            self.checkbutton[c] = tk.Checkbutton(self.channel_frame, text=c,variable=self.check_var[c])
            self.checkbutton[c].grid(row=int(x/8), column=int(x%8), sticky=tk.N + tk.S + tk.E + tk.W)
            if not c == 'M':
                self.checkbutton[rc] = tk.Checkbutton(self.channel_frame, text=rc, variable=self.check_var[rc])
                self.checkbutton[rc].grid(row=int(x/8), column=int((x%8)+1), sticky=tk.N + tk.S + tk.E + tk.W)
            x += 2
        
        self.check_label = tk.Label(self.channel_frame, text='Up to Order')
        self.check_label.grid(row=6, column=3, columnspan=2, sticky=tk.N + tk.S + tk.E + tk.W)
        self.order_box = tk.Spinbox(self.channel_frame, from_=0, to=5)
        self.order_box.grid(row=6, column=5, columnspan=3, sticky=tk.N + tk.S + tk.E + tk.W)
        self.order_button = tk.Button(self.channel_frame, text='Check Selected', command=self.check_selected)
        self.order_button.grid(row=7, column=4, columnspan = 4, sticky=tk.N + tk.S + tk.E + tk.W)
        self.check_all = tk.Button(self.channel_frame, text='Check all', command=self.check)
        self.check_all.grid(row=7, column=0, columnspan = 2, sticky=tk.N + tk.S + tk.E + tk.W)
        self.uncheck_all = tk.Button(self.channel_frame, text='Uncheck all', command=self.uncheck)
        self.uncheck_all.grid(row=7, column=2, columnspan = 2, sticky=tk.N + tk.S + tk.E + tk.W)
        
        #Characteristics Fields
        self.char_frame = ttk.LabelFrame(self.form_frame, text="Characteristics", relief=tk.RIDGE)
        self.char_frame.pack(side=tk.TOP, fill = tk.BOTH, expand = tk.YES)
        tk.Grid.columnconfigure(self.char_frame, 2, weight=1)
        tk.Grid.columnconfigure(self.char_frame, 4, weight=1)
        
        self.center_label = tk.Label(self.char_frame, text='Length')
        self.center_label.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(self.char_frame, 0, 1, 'L_Low')
        self.make_entry(self.char_frame, 0, 3, 'L_High')
        
        self.center_label = tk.Label(self.char_frame, text='Width')
        self.center_label.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(self.char_frame, 1, 1, 'W_Low')
        self.make_entry(self.char_frame, 1, 3, 'W_High')
        
        self.center_label = tk.Label(self.char_frame, text='Height')
        self.center_label.grid(row=2, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(self.char_frame, 2, 1, 'H_Low')
        self.make_entry(self.char_frame, 2, 3, 'H_High')
        
        self.make_entry(self.char_frame, 3, 1, 'Corona')
        self.make_entry(self.char_frame, 3, 3, 'Climit')
        
        
        
        #Start Button and Iteration control
        self.button_frame = ttk.LabelFrame(self.window, text="Start Meassurement", relief=tk.RIDGE)
        self.button_frame.pack(side=tk.TOP, fill=tk.BOTH, expand = tk.NO)
        tk.Grid.columnconfigure(self.button_frame, 1, weight=1)
        
        self.make_entry(self.button_frame, 0, 0, 'Csv_path')
        self.entries['Csv_path'].config(state='disabled')
        self.csv_button = tk.Button(self.button_frame, text='Browse', command=self.browse_csv, state='disabled')
        self.csv_button.grid(row = 0, column = 2, sticky=tk.N + tk.S + tk.E + tk.W)
        self.csv_value = tk.IntVar()
        self.csv_check = tk.Checkbutton(self.button_frame, text='Use CSV', variable=self.csv_value, command=self.csv_change)
        self.csv_check.grid(row = 0, column = 3, sticky=tk.N + tk.S + tk.E + tk.W)
        self.repeat_label = tk.Label(self.button_frame, text = 'Iterations')
        self.repeat_label.grid(row = 1, column = 0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.entries['Iterations'] = tk.Spinbox(self.button_frame, from_=1, to=10)
        self.entries['Iterations'].grid(row = 1, column = 1, columnspan=2, sticky=tk.N + tk.S + tk.E + tk.W)
        self.start_button = tk.Button(self.button_frame, text='Start', command=self.start)
        self.start_button.grid(row = 1, column = 3, rowspan=2, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(self.button_frame, 2, 0, 'Dest_path')
        self.dest_button = tk.Button(self.button_frame, text='Browse', command=self.browse_destination)
        self.dest_button.grid(row = 2, column = 2, sticky=tk.N + tk.S + tk.E + tk.W)
        
        
        self.fill_form()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.scan.__exit__(exc_type, exc_val, exc_tb)
        except AttributeError:
            pass
        try:
            self.loop_bool = False
        except AttributeError:
            pass
        return
    
    def process_message_queue(self, event):
        while self.message_queue.empty() is False:
            message = self.message_queue.get(block=False)
            print(message)
            
    def send_message_to_ui(self, message):
        self.message_queue.put(message)
        self.window.event_generate(self.message_event, when='tail')
    
    def csv_change(self):
        if self.csv_value.get() == 1:
            self.entries['Csv_path'].config(state='normal')
            self.csv_button.config(state='normal')
        else:
            self.entries['Csv_path'].config(state='disabled')
            self.csv_button.config(state='disabled')
        
    def make_entry(self, parent, r, c, name, labelspan=1, entryspan=1):
        self.labels[name] = tk.Label(parent, text=name)
        self.labels[name].grid(row=r, column=c, columnspan=labelspan, sticky=tk.N + tk.S + tk.E + tk.W)
        self.entries[name] = tk.Entry(parent)
        self.entries[name].grid(row=r, column=c+labelspan, columnspan=entryspan, sticky=tk.N + tk.S + tk.E + tk.W)
        
    def check(self):
        for button in self.checkbutton.keys():
            self.checkbutton[button].select()
        
    def uncheck(self):
        for button in self.checkbutton.keys():
            self.checkbutton[button].deselect()
    
    def check_selected(self):
        selection = int(self.order_box.get())
        for button in self.checkbutton.keys():
            if 'Z' in button or 'M' == button:
                self.checkbutton[button].select()
            else:
                order = button.split('-')[-1][1]
                if int(order) <= selection:
                    self.checkbutton[button].select()
                else:
                    self.checkbutton[button].deselect()
    
    def open_config(self):
        selected = False
        aborted = False
        while not selected and not aborted:
            name = filedialog.askopenfilename(filetypes=(("Config Files","*.ini"), ("All Files", "*.*")))
            try:
                self.scan_dict = read_config(name)
                selected = True
            except (cfg.MissingSectionHeaderError, ValueError, TypeError):
                if name:
                    messagebox.showerror("File Error", "The selected File is not a valid Config File. Please select a valid File.")
                else:
                    aborted = True
        if not aborted:
            self.fill_form()
        
    def save_config(self):
        f = filedialog.asksaveasfilename(filetypes=(('Config Files', '*.ini'), ("All Files", "*.*")))
        if not f: # asksaveasfile return `None` if dialog closed with "cancel".
            return
        else:
            self.update_dict()
            new_dict = self.scan_dict
            for key in self.scan_dict.keys():
                for val in self.scan_dict[key]:
                    if isinstance(self.scan_dict[key][val], list):
                        new_dict[key][val] = ';'.join(self.scan_dict[key][val])

            with open(f, 'w') as file:
                config = cfg.ConfigParser()
                config.read_dict(new_dict)
                config.write(file)
            
            self.scan_dict = read_config(f)
            new_dict = None
                
    def update_dict(self):
        for key in self.scan_dict['Info'].keys():
            self.scan_dict['Info'][key] = self.entries[key.capitalize()].get()

        for key in self.scan_dict['AFM'].keys():
            self.scan_dict['AFM'][key] = self.entries[key.capitalize()].get()

        for key in self.scan_dict['Fourier'].keys():
            self.scan_dict['Fourier'][key] = self.entries[key.capitalize()].get()

        for key in self.scan_dict['Channel'].keys():
            self.scan_dict['Channel'][key] = self.check_var[key.upper()].get()

        for key in self.scan_dict['Characteristics'].keys():
            if isinstance(self.scan_dict['Characteristics'][key], list):
                low = key[0].capitalize() + '_Low'
                high = key[0].capitalize() + '_High'
                self.scan_dict['Characteristics'][key] = [self.entries[low].get(), self.entries[high].get()]
                print(low, high)
            else:
                self.scan_dict['Characteristics'][key] = self.entries[key.capitalize()].get()
        
        for key in self.scan_dict['Measurement'].keys():
            self.scan_dict['Measurement'][key] = self.entries[key.capitalize()].get()
    
    def fill_form(self):
        for key in self.scan_dict['Info'].keys():
            if isinstance(self.scan_dict['Info'][key], list):
                self.set_text(key.capitalize(), '; '.join(self.scan_dict['Info'][key]))
            else:
                self.set_text(key.capitalize(), self.scan_dict['Info'][key])
        
        for key in self.scan_dict['AFM'].keys():
            self.set_text(key.capitalize(), self.scan_dict['AFM'][key])
            
        for key in self.scan_dict['Fourier'].keys():
            if key == 'angle' or key == 't_int':
                self.set_text(key.capitalize(), self.scan_dict['AFM'][key])
            else:
                self.set_text(key.capitalize(), self.scan_dict['Fourier'][key])
        
        for key in self.scan_dict['Channel'].keys():
            if self.scan_dict['Channel'][key] == 0:
                self.checkbutton[key.upper()].deselect()
            else:
                self.checkbutton[key.upper()].select()
        
        for key in self.scan_dict['Characteristics'].keys():
            if isinstance(self.scan_dict['Characteristics'][key], list):
                low = key[0].capitalize() + '_Low'
                high = key[0].capitalize() + '_High'
                self.set_text(low, self.scan_dict['Characteristics'][key][0])
                self.set_text(high, self.scan_dict['Characteristics'][key][1])
            else:
                self.set_text(key.capitalize(), self.scan_dict['Characteristics'][key])
        
        for key in self.scan_dict['Measurement'].keys():
            self.set_text(key.capitalize(), self.scan_dict['Measurement'][key])
                
    def set_text(self, name, text):
        self.entries[name].delete(0, tk.END)
        self.entries[name].insert(0, text)
    
    def make_ini(self):
        config = cfg.ConfigParser()
        config['Info'] = {'project': 'Projectname', 'description': 'Description', 
                          'operators': 'Operators'}
        config['AFM'] = {'x0': 50, 'y0': 50, 'dx': 15, 'dy': 15, 'px': 151,
                         'py': 151, 'angle': 0, 't_int': 11.9, 'setpoint': 0.8,
                         'hlimit': 0.65}
        config['Fourier'] = {'x_res': 1, 'y_res': 1, 'angle': 0, 't_int': 11.9,
                             'offset': 730, 'distance': 100, 'averaging': 5,
                             'resolution': 512, 'source': 'Synchrotron'}
        config['Channel'] = {'Z': 1, 'M': 1, 'M0A': 1, 'M0P': 1, 'O0A': 1, 'O0P': 1,
                             'M1A': 1, 'M1P': 1, 'O1A': 1, 'O1P': 1, 'M2A': 1, 'M2P': 1, 'O2A': 1,
                             'O2P': 1, 'M3A': 1, 'M3P': 1, 'O3A': 1, 'O3P': 1, 'M4A': 1, 'M4P': 1,
                             'O4A': 1, 'O4P': 1, 'M5A': 1, 'M5P': 1, 'O5A': 1, 'O5P': 1, 'R-Z': 1,
                             'R-M0A': 1, 'R-M0P': 1, 'R-O0A': 1, 'R-O0P': 1, 'R-M1A': 1, 'R-M1P': 1,
                             'R-O1A': 1, 'R-O1P': 1, 'R-M2A': 1, 'R-M2P': 1, 'R-O2A': 1, 'R-O2P': 1,
                             'R-M3A': 1, 'R-M3P': 1, 'R-O3A': 1, 'R-O3P': 1, 'R-M4A': 1, 'R-M4P': 1,
                             'R-O4A': 1, 'R-O4P': 1, 'R-M5A': 1, 'R-M5P': 1, 'R-O5A': 1, 'R-O5P': 1}
        config['Characteristics'] = {'Length': '1.8; 5', 'Width': '0.5; 1.3',
                                     'Height': '0.4; 0.65', 'Corona': 0.5, 'CLimit': 0.2}
        config['Measurement'] = {'Iterations': 1, 'dest_path': os.getcwd(), 'csv_path': ''}
        with open(self.scan, 'w') as file:
            config.write(file)
            
    def browse_destination(self):
        dirname = filedialog.askdirectory(initialdir=os.getcwd(),title='Please select a destination for the HDF5 Files')
        if not dirname:
            return
        else:
            self.entries['Dest_path'].delete(0, tk.END)
            self.entries['Dest_path'].insert(0, dirname)
            
    def browse_csv(self):
        dirname = filedialog.askdirectory(initialdir=os.getcwd(),title='Please select a directory in which there are the CSV Files')
        if not dirname:
            return
        else:
            self.entries['Csv_path'].delete(0, tk.END)
            self.entries['Csv_path'].insert(0, dirname)
                
    def toggle_fullscreen(self, event=None):
        self.state = not self.state  # Just toggling the boolean
        self.window.attributes("-fullscreen", self.state)
        return "break"
    
    def end_fullscreen(self, event=None):
        self.state = False
        self.window.attributes("-fullscreen", False)
        return "break"
            
    def pause_meas(self):
        if self.meas_paused:
            print('Resuming...')
            self.window_pause_txt.set('Pause')
            self.meas_paused = False
            self.scan.pause()
        else:
            print('Pausing...')
            self.window_pause_txt.set('Resume')
            self.meas_paused = True
    
    def start(self):
        self.start_button.config(state='disabled')
        self.scan_window = tk.Toplevel(self.window)
        self.window_text = tk.Text(self.scan_window, wrap='word', height = 11, width=50)
        self.window_text.grid(column=0, row=0, columnspan = 2, sticky='NSWE', padx=5, pady=5)
        self.meas_paused = False
        self.window_pause_txt = tk.StringVar()
        self.window_pause = tk.Button(self.scan_window, textvariable=self.window_pause_txt, command=self.pause_meas)
        self.window_pause_txt.set('Pause')
        self.window_pause.grid(column=0, row=1, sticky='NSWE', padx=5, pady=5)
        #sys.stdout = StdoutRedirector(self.window_text, sys.stdout)
        self.update_dict()
        self.scan = Scan(copy.deepcopy(self.scan_dict))
        self.scan_thread = threading.Thread(target=self.scan.start_scan, args=(self.entries['Csv_path'].get()))
        self.scan_thread.start()

with start_scan() as scan:
    scan.window.mainloop()
