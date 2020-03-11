import tkinter as tk
from tkinter import ttk
import copy
import sys
from StdoutRedirector import *
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.animation as animation
import numpy as np
from Nanorod import *
import h5py as hdf5
from PIL import Image
import io
import gc


class Nanorod_GUI(tk.Tk):
    
    def __init__(self):
        self.meas_paused = False
        self.progress = tk.DoubleVar()
        self.scan_dict = {}
        self.images = {}
        self.scan_completed = False
        self.observers = []
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.scan_aborted = True
        sys.stdout = sys.__stdout__
        print('Exit')
        self.scan_completed = True
        try:
            self.scan.__exit__('blosnichtabort', None, None)
        except AttributeError:
            pass
        self.scan_window.destroy()
        
    def bind_to(self, callback):
        self.observers.append(callback)
    
    def close_window(self):
        self.__exit__(None, None, None)

    def pass_dict(self, adict):
        self.scan_dict = adict
    
    def reset(self):
        gc.collect()
        self.__init__()
        
        
    def create_window(self, parent):
        self.scan_window = tk.Toplevel(parent)
        self.scan_window.protocol("WM_DELETE_WINDOW", self.close_window)
        window_text = tk.Text(self.scan_window, wrap='word', height = 11, width=50)
        window_text.grid(column=0, row=3, columnspan = 2, sticky='NSWE')
        sys.stdout = StdoutRedirector(window_text, sys.stdout)
        
        self.window_pause_txt = tk.StringVar()
        window_pause = tk.Button(self.scan_window, textvariable=self.window_pause_txt, command=self.pause_meas)
        self.window_pause_txt.set('Pause')
        window_pause.grid(column=1, row=6, columnspan=2, sticky='NSWE')
        self.progress.set(0)
        window_progress = ttk.Progressbar(self.scan_window, orient="horizontal", length=300, mode="determinate", variable=self.progress, maximum=1)
        window_progress.grid(column=0, row=4, columnspan = 5, sticky='NSWE')
        num_of_px = self.scan_dict['AFM']['Px'] * self.scan_dict['AFM']['Py']
        self.window_percent = tk.StringVar()
        self.window_percent.set('0 / {}'.format(int(num_of_px)))
        window_percent_label = tk.Label(self.scan_window, textvariable=self.window_percent)
        window_percent_label.grid(column=1, row=5, columnspan=2, sticky='NSWE')
        
        #GUI for Previews
        live_plot = tk.Label(self.scan_window, relief='sunken')
        live_plot.grid(column=0, row=1, columnspan=3, sticky='NSWE')
        self.fig = plt.figure(figsize=(10, 4), dpi=100)
        self.ax = self.fig.add_subplot(1,1,1)
        self.ax.yaxis.set_visible(False)
        self.ax.xaxis.set_visible(False)
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master = live_plot)
        self.canvas._tkcanvas.pack(side = tk.TOP, fill = tk.BOTH, expand = 1)
        self.avrg_pointer = 0
        self.plot_data = np.zeros((1, 100))
        self.ani = animation.FuncAnimation(self.fig, self.animate_plot, interval=100)
        self.plot_select = ttk.Combobox(self.scan_window, values=[x.upper() for x in self.scan_dict['Channel'].keys() if self.scan_dict['Channel'][x] == 1], state='readonly')
        self.plot_select.grid(column=2, row=0, sticky='NSW')
        self.plot_select.set('O2A')
        self.plot_select.bind("<<ComboboxSelected>>", self.set_plot_channel)
        
        self.images['live_afm'] = tk.PhotoImage(master=self.scan_window)
        self.images['img_view'] = tk.PhotoImage(master=self.scan_window)
        
        self.live_image = tk.Label(self.scan_window, relief='sunken', image=self.images['live_afm'])
        self.live_image.grid(column=2, row=3, columnspan=1, sticky='NSWE')
        live_select_label = tk.Label(self.scan_window, text='Live Channel:')
        live_select_label.grid(column=2, row=2, sticky='NSW')
        live_select = ttk.Combobox(self.scan_window, values=[x.upper() for x in self.scan_dict['Channel'].keys() if self.scan_dict['Channel'][x] == 1], state='readonly')
        live_select.grid(column=2, row=2, sticky='NSW')
        live_select.current(0)
        live_select.bind("<<ComboboxSelected>>", self.set_afm_channel)
        
        self.iteration_count = tk.StringVar()
        self.iteration_count.set('Iterions: ')
        step_view_label = tk.Label(self.scan_window, textvariable=self.iteration_count)
        step_view_label.grid(column=3, row=0, sticky='NSW')
        self.step_view = tk.Listbox(self.scan_window, {'fg': 'red'})
        self.step_view.bind('<Double-1>', self.step_select)
        self.step_view.grid(column=3, row=1, rowspan=3, sticky='NSWE')
        step_scroll_ver = tk.Scrollbar(self.scan_window, orient='vertical')
        step_scroll_ver.grid(column=4, row=1, rowspan=3, sticky='NSW')
        step_scroll_ver.config(command=self.step_view.yview)
        self.step_view.config(yscrollcommand=step_scroll_ver.set)
        
    def pause_meas(self):
        print('Pause')
        
    def update_progress(self, progress):
        self.progress.set(progress)
        self.window_percent.set('{} / {}'.format(int(progress * self.num_of_px), int(self.num_of_px)))
    
    def update_image(self, name, image):
        with io.BytesIO() as output:
            Image.fromarray(image).save(output, format='GIF')
            self.images[name].put(output.getvalue())
    
    def update_plot(self, raw):
        self.plot_data = asNumpyArray(raw)[0, 0]
    
    def animate_plot(self, i):
        self.ax.clear()
        for x in range(len(self.plot_data)-1, 0, -1):
            if not all(np.isnan(self.plot_data[x])):
                self.avrg_pointer = x
                break
        if self.avrg_pointer > 0:
            self.ax.plot(self.plot_data[self.avrg_pointer-1], 'b', linewidth=0.5, alpha=0.2)
        self.ax.plot(self.plot_data[self.avrg_pointer], 'r', linewidth=0.5)
        
    def check_for_epics(self):
        epics_ctrl = Epics_Control()
        epics_ctrl.bind_to(self.send_message_to_ui)
    
    def set_plot_channel(self, *args):
        print('Set plot channel')
        
    def set_afm_channel(self, *args):
        print('Set AFM Channel')
    
    def step_select(self, *args):
        selection = self.step_view.curselection()
        try:
            item = self.step_view.get(selection[0])
        except IndexError:
            pass
        else:
            if self.step_view.itemcget(selection[0], 'fg') == 'green':
                if 'interferogram' in item.lower():
                    self.plot_data = self.scan.get_plot_image(item, self.plot_select.get())
                else:
                    self.update_image('img_view', self.scan.get_step_image(item, self.live_select.get()))
                    self.live_image.configure(image=self.images['img_view'])
            else:
                if 'interferogram' in item.lower():
                    self.scan.set_live_plot(True)
                else:
                    self.live_image.configure(image=self.images['live_afm'])
                    
                
    def update_image(self, name, image):
        with io.BytesIO() as output:
            Image.fromarray(image).save(output, format='GIF')
            self.images[name].put(output.getvalue())
    
    def add_step(self, text):
        self.step_view.insert(tk.END, text)
    
    def finish_step(self, text):
        try:
            position = self.step_view.get(0, tk.END).index(text)
            self.step_view.itemconfig(position, {'fg': 'green'})
        except ValueError:
            pass
                    
    def start_scan(self):
        count = int(self.scan_dict['Control']['Iterations'])
        self.scan_aborted = False
        for x in range(count):
            if not self.scan_completed:
                self.iteration_count.set('Iteration: ' + str(x+1) + '/' + str(count))
                self.scan = Scan(copy.deepcopy(self.scan_dict))
                self.scan.bind_to('live_afm', self.update_image)
                self.scan.bind_to('img_view', self.update_image)
                self.scan.bind_to('plot_view', self.update_plot)
                self.scan.bind_to('progress', self.update_progress)
                self.scan.bind_to('live_plot', self.update_plot)
                self.scan.bind_to('add_step', self.add_step)
                self.scan.bind_to('finish_step', self.finish_step)
                self.scan.full_scan(x+1, '')
                self.scan.__exit__(None, None, None)
        if not self.scan_aborted:
            print('Alles Fertig')
            for callback in self.observers:
                callback('quit_scan', 'Nanorod')
        self.scan_completed = True
