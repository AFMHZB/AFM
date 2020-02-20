import configparser as cfg

class ConfigHandler(object):
    def __init__(self):
        self.config = cfg.ConfigParser()
        
    def read_config(self, path, keys):
        config.read(path)
        flag = all(key in config.sections() for key in keys) and all(key in keys for key in config.sections())
        if not config_flag:
            raise ValueError('Wrong or Corrupted Config')
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
        return new_dict
    
    def write_config(self, path, adict):
        new_dict = adict
        for key in adict.keys():
            for val in adict[key]:
                if isinstance(adict[key][val], list):
                    new_dict[key][val] = ';'.join([str(x) for x in adict[key][val]])

        with open(path, 'w') as file:
            config = cfg.ConfigParser()
            config.read_dict(new_dict)
            config.write(file)
            
    def path_dialog_save(self):
        print('Save a file')
        
    def path_dialog_read(self):
        print('Read a file')
