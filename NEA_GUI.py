import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from ConfigHandler import ConfigHandler
import queue
from Nanorod_GUI import *
import threading
from Epics_Control import Epics_Control


class NEA_GUI(tk.Tk):
    def __init__(self):
        self.NEA_GUI_TABS = ['Nanorod', 'Compressed Sensing', 'Hyperspectral', 'Complete Scan']
        self.scan_dict = {x:{} for x in self.NEA_GUI_TABS}
        self.entries = {x:{} for x in self.NEA_GUI_TABS}
        self.checkbutton = {}
        self.config_handler = ConfigHandler()
        self.make_Main_Window()
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.scan.__exit__('abort', exc_val, exc_tb)
        except (AttributeError, RecursionError):
            pass
        try:
            self.loop_var = False
        except AttributeError:
            pass
        return
        
    def make_Main_Window(self):
        self.window = tk.Tk()
        self.window.title("Automatic neaSNOM Meassurement")
        self.window['padx'] = 5
        self.window['pady'] = 5
        self.window.resizable(False, False)
        self.message_queue = queue.Queue()
        self.message_event = '<<message>>'
        self.window.bind(self.message_event, self.process_message_queue)
        style = ttk.Style()
        style.configure('TLabelframe', background='White')   
        style.configure('TLabelframe.Label', background='White')
        
        menu = tk.Menu(self.window)
        self.window.config(menu=menu)
        filemenu = tk.Menu(menu)
        menu.add_cascade(label="Program", menu=filemenu)
        filemenu.add_command(label="Load Config", command=self.open_config)
        filemenu.add_command(label="Save Config", command=self.save_config)
        filemenu.add_command(label='Reset', command=self.fill_form)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.window.destroy)
        
        self.notebook = ttk.Notebook(self.window)
        self.tabs = {}
        for tab in self.NEA_GUI_TABS:
            self.tabs[tab] = ttk.Frame(self.notebook)
            self.notebook.add(self.tabs[tab], text=tab)
        self.notebook.pack(expand=1, fill='both')
        
        self.make_Frame(self.tabs['Nanorod'], 'Setup Nanorod Meassurement', ['info', 'afm', 'fourier', 'channel', 'characteristics', 'control'])
        self.make_Frame(self.tabs['Hyperspectral'], 'Setup Hyperspectral Scan', ['info', 'afm', 'fourier', 'channel', 'control'])
        self.make_Frame(self.tabs['Compressed Sensing'], 'Setup Compressed Sensing', ['info', 'afm', 'channel', 'control'])
        self.make_Frame(self.tabs['Complete Scan'], 'Setup Complete Scan', ['info', 'afm', 'fourier'])
        
        self.scan_class = {}
        self.scan_class['Nanorod'] = Nanorod_GUI()
        
        for key in self.scan_class:
            self.scan_class[key].bind_to(self.send_message_to_ui)
        
        self.notebook.bind("<<NotebookTabChanged>>", self.update_dict)
        self.update_dict()
        
        
    def make_Frame(self, parent, name, boxlist):
        frame = ttk.LabelFrame(parent, text=name, relief=tk.RIDGE)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand = tk.YES)
        plabel = self.notebook.tab(parent)['text']
        
        if 'info' in boxlist:
            self.Info_Box(frame, plabel)
        if 'afm' in boxlist:
            self.AFM_Box(frame, plabel)
        if 'fourier' in boxlist:
            self.Fourier_Box(frame, plabel)
        if 'channel' in boxlist:
            self.Channel_Box(frame, plabel)
        if 'characteristics' in boxlist:
            self.Characteristics_Box(frame, plabel)
        if 'control' in boxlist:
            self.Control_Box(frame, plabel)
        
    def make_Base_Frame(self, parent, plabel, text):
        frame = ttk.LabelFrame(parent, text=text, relief=tk.RIDGE)
        frame.pack(side=tk.TOP, fill = tk.BOTH, expand = tk.NO)
        tk.Grid.columnconfigure(frame, 2, weight=1)
        tk.Grid.columnconfigure(frame, 4, weight=1)
        self.entries[plabel][text] = {}
        return frame
    
    #Create two Column Entry with a Label in first Column and the Entry in Second
    def make_entry(self, parent, plabel, section, r, c, name, labelspan=1, entryspan=1):
        label = tk.Label(parent, text=name)
        label.grid(row=r, column=c, columnspan=labelspan, sticky=tk.N + tk.S + tk.E + tk.W)
        self.entries[plabel][section][name] = tk.StringVar()
        entry = tk.Entry(parent, textvariable=self.entries[plabel][section][name])
        entry.grid(row=r, column=c+labelspan, columnspan=entryspan, sticky=tk.N + tk.S + tk.E + tk.W)
        
    def Control_Box(self, parent, plabel):
        box_name = "Control"
        self.entries[plabel][box_name] = {}
        button_frame = ttk.LabelFrame(parent, text=box_name, relief=tk.RIDGE)
        button_frame.pack(side=tk.TOP, fill=tk.BOTH, expand = tk.NO)
        tk.Grid.columnconfigure(button_frame, 1, weight=1)
        
        repeat_label = tk.Label(button_frame, text = 'Iterations')
        repeat_label.grid(row = 0, column = 0, sticky='NSWE')
        self.entries[plabel][box_name]['Iterations'] = tk.IntVar()
        iter_control = tk.Spinbox(button_frame, textvariable=self.entries[plabel][box_name]['Iterations'], from_=1, to=10)
        iter_control.grid(row = 0, column = 1, columnspan=1, sticky='NSWE')
        self.entries[plabel][box_name]['Epics'] = tk.IntVar()
        self.epics_check_button = {}
        self.epics_check_button[plabel] = tk.Checkbutton(button_frame, text='Epics Control', variable=self.entries[plabel][box_name]['Epics'])
        self.epics_check_button[plabel].grid(row = 0, column = 2, sticky = 'NSWE')
        self.start_button = tk.Button(button_frame, text='Start', command=self.start)
        self.start_button.grid(row = 0, column = 3, columnspan=2, rowspan=2, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(button_frame, plabel, box_name , 1, 0, 'Dest_path')
        self.dest_button = tk.Button(button_frame, text='Browse', command=self.browse_destination)
        self.dest_button.grid(row = 1, column = 2, sticky= 'NSWE')
    
    #Create AFM Entry Box
    def AFM_Box(self, parent, plabel):
        box_name = 'AFM'
        afm_frame = self.make_Base_Frame(parent, plabel, box_name)
        
        center_label = tk.Label(afm_frame, text='Center')
        center_label.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(afm_frame, plabel, box_name, 0, 1, 'X0')
        self.make_entry(afm_frame, plabel, box_name, 0, 3, 'Y0')
        self.entries[plabel][box_name]['X0'].trace('w', lambda *_: self.entries[plabel][box_name]['Y0'].set(self.entries[plabel][box_name]['X0'].get()))
        
        area_label = tk.Label(afm_frame, text='Area')
        area_label.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(afm_frame, plabel, box_name, 1, 1, 'Dx')
        self.make_entry(afm_frame, plabel, box_name, 1, 3, 'Dy')
        self.entries[plabel][box_name]['Dx'].trace('w', lambda *_: self.entries[plabel][box_name]['Dy'].set(self.entries[plabel][box_name]['Dx'].get()))
        
        res_label = tk.Label(afm_frame, text='Resolution')
        res_label.grid(row=2, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(afm_frame, plabel, box_name, 2, 1, 'Px')
        self.make_entry(afm_frame, plabel, box_name, 2, 3, 'Py')
        self.entries[plabel][box_name]['Px'].trace('w', lambda *_: self.entries[plabel][box_name]['Py'].set(self.entries[plabel][box_name]['Px'].get()))
        
        self.make_entry(afm_frame, plabel, box_name, 3, 1, 'Angle')
        self.make_entry(afm_frame, plabel, box_name, 3, 3, 'T_int')
        self.make_entry(afm_frame, plabel, box_name, 4, 1, 'Setpoint')
        self.make_entry(afm_frame, plabel, box_name, 4, 3, 'Hlimit')
        
    #Create Fourier Entry Box
    def Fourier_Box(self, parent, plabel):
        box_name = 'Fourier'
        fourier_frame = self.make_Base_Frame(parent, plabel, box_name)
        
        point_label = tk.Label(fourier_frame, text='Resolution')
        point_label.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(fourier_frame, plabel, box_name, 0, 1, 'X_res')
        self.make_entry(fourier_frame, plabel, box_name, 0, 3, 'Y_res')
        self.entries[plabel][box_name]['X_res'].trace('w', lambda *_: self.entries[plabel][box_name]['Y_res'].set(self.entries[plabel][box_name]['X_res'].get()))
        
        int_label = tk.Label(fourier_frame, text='Interferometer')
        int_label.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(fourier_frame, plabel, box_name, 1, 1, 'Offset')
        self.make_entry(fourier_frame, plabel, box_name, 1, 3, 'Distance')
        
        self.make_entry(fourier_frame, plabel, box_name, 2, 1, 'Averaging')
        self.make_entry(fourier_frame, plabel, box_name, 2, 3, 'Resolution')
        
        self.make_entry(fourier_frame, plabel, box_name, 3, 1, 'Angle_f')
        self.make_entry(fourier_frame, plabel, box_name, 3, 3, 'T_int_f')
        
        self.make_entry(fourier_frame, plabel, box_name, 4, 1, 'Source', 1, 3)
    
    def Channel_Box(self, parent, plabel):
        box_name = 'Channel'
        self.entries[plabel][box_name] = {}
        channel = ['Z', 'M0A', 'M1A', 'M2A', 'M3A', 'M4A', 'M5A', 'M0P', 'M1P', 'M2P', 'M3P', 'M4P', 'M5P',
                  'O0A', 'O1A', 'O2A', 'O3A', 'O4A', 'O5A', 'O0P', 'O1P', 'O2P', 'O3P', 'O4P', 'O5P', 'M']
        channel_frame = ttk.LabelFrame(parent, text=box_name, relief=tk.RIDGE)
        channel_frame.pack(side=tk.TOP, fill = tk.BOTH, expand = tk.NO)
        for i in range(8):
            tk.Grid.columnconfigure(channel_frame, i, weight=1)
            
        self.checkbutton[plabel] = {}
        x = 0
        for c in channel:
            rc = 'R-' + c
            self.entries[plabel][box_name][c] = tk.IntVar()
            self.checkbutton[plabel][c] = tk.Checkbutton(channel_frame, text=c,variable=self.entries[plabel][box_name][c])
            self.checkbutton[plabel][c].grid(row=int(x/8), column=int(x%8), sticky=tk.N + tk.S + tk.E + tk.W)
            if not c == 'M':
                self.entries[plabel][box_name][rc] = tk.IntVar()
                self.checkbutton[plabel][rc] = tk.Checkbutton(channel_frame, text=rc, variable=self.entries[plabel][box_name][rc])
                self.checkbutton[plabel][rc].grid(row=int(x/8), column=int((x%8)+1), sticky=tk.N + tk.S + tk.E + tk.W)
            x += 2
        
        check_label = tk.Label(channel_frame, text='Up to Order')
        check_label.grid(row=6, column=3, columnspan=2, sticky=tk.N + tk.S + tk.E + tk.W)
        self.order_box = tk.Spinbox(channel_frame, from_=0, to=5)
        self.order_box.grid(row=6, column=5, columnspan=3, sticky=tk.N + tk.S + tk.E + tk.W)
        order_button = tk.Button(channel_frame, text='Check Selected', command=self.check_selected)
        order_button.grid(row=7, column=4, columnspan = 4, sticky=tk.N + tk.S + tk.E + tk.W)
        check_all = tk.Button(channel_frame, text='Check all', command=self.check)
        check_all.grid(row=7, column=0, columnspan = 2, sticky=tk.N + tk.S + tk.E + tk.W)
        uncheck_all = tk.Button(channel_frame, text='Uncheck all', command=self.uncheck)
        uncheck_all.grid(row=7, column=2, columnspan = 2, sticky=tk.N + tk.S + tk.E + tk.W)
        
    def check(self):
        plabel = self.notebook.tab(self.notebook.select())['text']
        for button in self.checkbutton[plabel].keys():
            self.checkbutton[plabel][button].select()
        
    def uncheck(self):
        plabel = self.notebook.tab(self.notebook.select())['text']
        for button in self.checkbutton[plabel].keys():
            self.checkbutton[plabel][button].deselect()
    
    def check_selected(self):
        plabel = self.notebook.tab(self.notebook.select())['text']
        selection = int(self.order_box.get())
        for button in self.checkbutton[plabel].keys():
            if 'Z' in button or 'M' == button:
                self.checkbutton[plabel][button].select()
            else:
                order = button.split('-')[-1][1]
                if int(order) <= selection:
                    self.checkbutton[plabel][button].select()
                else:
                    self.checkbutton[plabel][button].deselect()
        
    def Characteristics_Box(self, parent, plabel):
        box_name = 'Characteristics'
        char_frame = self.make_Base_Frame(parent, plabel, box_name)
        
        center_label = tk.Label(char_frame, text='Length')
        center_label.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(char_frame, plabel, box_name, 0, 1, 'L_Low')
        self.make_entry(char_frame, plabel, box_name, 0, 3, 'L_High')
        
        center_label = tk.Label(char_frame, text='Width')
        center_label.grid(row=1, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(char_frame, plabel, box_name, 1, 1, 'W_Low')
        self.make_entry(char_frame, plabel, box_name, 1, 3, 'W_High')
        
        center_label = tk.Label(char_frame, text='Height')
        center_label.grid(row=2, column=0, sticky=tk.N + tk.S + tk.E + tk.W)
        self.make_entry(char_frame, plabel, box_name, 2, 1, 'H_Low')
        self.make_entry(char_frame, plabel, box_name, 2, 3, 'H_High')
        
        self.make_entry(char_frame, plabel, box_name, 3, 1, 'Corona')
        self.make_entry(char_frame, plabel, box_name, 3, 3, 'Climit')
        
    def Info_Box(self, parent, plabel):
        box_name = 'Info'
        self.entries[plabel][box_name] = {}
        info_frame = ttk.LabelFrame(parent, text=box_name, relief=tk.RIDGE)
        info_frame.pack(side=tk.TOP, fill = tk.BOTH, expand = tk.NO)
        tk.Grid.columnconfigure(info_frame, 1, weight=1)
        
        self.make_entry(info_frame, plabel, box_name, 0, 0, 'Project')
        self.make_entry(info_frame, plabel, box_name, 1, 0, 'Description')
        self.make_entry(info_frame, plabel, box_name, 2, 0, 'Operators')
    
    def get_curr_frames(self):
        plabel = self.notebook.tab(self.notebook.select())['text']
        frames = self.tabs[plabel].winfo_children()[0].winfo_children()
        return plabel, frames
        
    def open_config(self):
        path = self.config_handler.path_dialog_read()
        if path:
            plabel, frames = self.get_curr_frames()
            self.scan_dict[plabel] = self.config_handler.read_from_file(path)
            if self.scan_dict[plabel].keys() == self.entries[plabel].keys():
                self.fill_form()
            else:
                print('Wrong or corrupted Config File selected.')
                print(self.scan_dict)
    
    def save_config(self):
        print('Save Config')
        plabel, _ = self.get_curr_frames()
        self.update_dict()
        path = self.config_handler.path_dialog_save()
        if path:
            self.config_handler.write_to_file(path, self.scan_dict[plabel])
        
    def fill_form(self):
        print('Fill Form')
        plabel, frames = self.get_curr_frames()
        frame_names = [child.cget('text') for child in frames]
        for sec in self.scan_dict[plabel]:
            for key in self.scan_dict[plabel][sec].keys():
                if isinstance(self.scan_dict[plabel][sec][key], list):
                    field = '; '.join(self.scan_dict[plabel][sec][key])
                else:
                    field = str(self.scan_dict[plabel][sec][key])
                self.entries[plabel][sec][key].set(field)
            
        if 'Channel' in frame_names:
            for key in self.checkbutton[plabel]:
                if self.entries[plabel]['Channel'][key].get() > 0:
                    self.checkbutton[plabel][key].select()
                else:
                    self.checkbutton[plabel][key].deselect()
        
    def update_dict(self, event=None):
        plabel, frames = self.get_curr_frames()
        frame_names = [child.cget('text') for child in frames]   
        self.scan_dict[plabel] = {x:{} for x in frame_names}
        for sec in self.entries[plabel].keys():
            for key in self.entries[plabel][sec].keys():
                try:
                    self.scan_dict[plabel][sec][key] = float(self.entries[plabel][sec][key].get())
                except ValueError:
                    self.scan_dict[plabel][sec][key] = self.entries[plabel][sec][key].get()
                
    def browse_destination(self):
        dirname = self.config_handler.path_dialog_dir()
        plabel, _ = self.get_curr_frames()
        if dirname:
            self.entries[plabel]['Control']['Dest_path'].set(dirname)
                
    #Communication with GUI
    def send_message_to_ui(self, message, data=None):
        self.message_queue.put((message, data))
        self.window.event_generate(self.message_event, when='tail')

    def process_message_queue(self, event):
        while self.message_queue.empty() is False:
            message, data = self.message_queue.get(block=False)
            print(message)
            if message == 'quit_scan':
                sys.stdout = sys.__stdout__
                self.start_button.config(state='normal')
                try:
                    self.scan_class[data].close_window()
                    self.scan_class[data].reset()
                    self.scan_class[data].bind_to(self.send_message_to_ui)
                except AttributeError:
                    pass
            if message == 'pause_scan':
                self.pause_meas()
            if message == 'epics_stop':
                print('Detected Start of Injection.')
                try:
                    self.scan.set_wait_for_injection(True)
                except AttributeError:
                    pass
            if message == 'epics_restart':
                print('Injection is finished.')
                try:
                    self.scan.set_wait_for_injection(False)
                except AttributeError:
                    pass
            if message == 'epics_error':
                print('Detected Currency Drop. Old: {} - New: {}'.format(data[0], data[1]))
                try:
                    self.scan.set_wait_for_injection(True)
                except AttributeError:
                    pass
                
    def check_for_epics(self):
        epics_ctrl = Epics_Control()
        epics_ctrl.bind_to(self.send_message_to_ui)
                
    def start(self):
        self.start_button.config(state='disabled')
        self.update_dict()
        plabel, _ = self.get_curr_frames()
        self.scan_class[plabel].pass_dict(self.scan_dict[plabel])
        self.scan_window = self.scan_class[plabel].create_window(self.window)
        self.scan_thread = threading.Thread(target=self.scan_class[plabel].start_scan)#, args=(*args))
        self.scan_completed = False
        self.scan_thread.start()
        if self.scan_dict[plabel]['Control']['Epics'] > 0:
            self.epics_thread = threading.Thread(target=self.check_for_epics)
            self.epics_thread.start()
                    
            
        
with NEA_GUI() as gui:
    gui.window.mainloop()
