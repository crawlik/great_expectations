class DataContext(object):
    def __init__(self, *args, **kwargs):
        self.connect(*args, **kwargs)

    def connect(self, connection_string):
        return NotImplementedError

    def list_datasets(self):
        return NotImplementedError

    def get_data_set(self, dataset_name):
        return NotImplementedError
