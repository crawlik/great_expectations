from .base import DataContext
from ..dataset.sqlalchemy_dataset import SqlAlchemyDataSet

from sqlalchemy import create_engine, MetaData

class SqlAlchemyDataContext(DataContext):

    def __init__(self, *args, **kwargs):
        super(SqlAlchemyDataContext, self).__init__(*args, **kwargs)

    def connect(self, connection_string):
        self.engine = create_engine(connection_string)

    def list_datasets(self):
        return MetaData.reflect(engine=self.engine).tables

    def get_data_set(self, dataset_name):
        return SqlAlchemyDataSet(self.engine, dataset_name)
