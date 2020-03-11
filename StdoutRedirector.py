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
