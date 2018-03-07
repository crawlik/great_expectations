from .base import DataContext
from great_expectations import read_csv

import glob

class PandasCSVDataContext(DataContext):

    def __init__(self, *args, **kwargs):
        super(PandasCSVDataContext, self).__init__(*args, **kwargs)

    def connect(self, connection_string):
        self.directory = connection_string

    def list_datasets(self):
        return glob.glob(self.directory)

    def get_data_set(self, dataset_name):
        df = read_csv(dataset_name)
        return df