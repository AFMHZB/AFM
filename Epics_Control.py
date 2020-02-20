import epics
import time  

class Epics_Control:
    def __init__(self):
        self.observer = []
        self.limit = 0.2
        self.paused = False
        self.writing = False
        self.cur_state = epics.caget('MLSOPCCP:curState')
        state = epics.PV('MLSOPCCP:curState')
        state.add_callback(self.on_change)
        self.cur_value = epics.caget('CUM1ZK3RP:rdCur')
        current = epics.PV('CUM1ZK3RP:rdCur')
        current.add_callback(self.on_change)
        
    def bind_to(self, callback):
        self.observer.append(callback)
        
    def on_change(self, pvname=None, value=None, char_value=None, **kws):
        if pvname == 'MLSOPCCP:curState':
            if self.cur_state == value:
                return
            if self.cur_state == 'IDLE':
                self.paused = True
                self.send_message('epics_stop')
            elif value == 'IDLE':
                time.sleep(60)
                self.send_message('epics_restart')
                self.paused = False
            self.cur_state = value
        elif pvname == 'CUM1ZK3RP:rdCur':
            if not self.paused:
                if abs(value) > abs(self.cur_value * (1+self.limit)) or abs(value) < abs(self.cur_value * (1-self.limit)):
                    self.paused = True
                    self.send_message(('epics_error', (cur_value, value)))
            self.cur_value = value
    
    def send_message(self, text):
        while self.writing:
            time.sleep(0.01)
        self.writing = True
        for callback in self.observer:
            callback(text)
        self.writing = False
