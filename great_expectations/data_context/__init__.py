from .SqlAlchemyDataContext import SqlAlchemyDataContext
from .PandasCSVDataContext import PandasCSVDataContext

def get_data_context(context_type, *args, **kwargs):
    if context_type == "sqlalchemy":
        return SqlAlchemyDataContext(args, kwargs)
    elif context_type == "pandas_directory":
        return PandasCSVDataContext(args, kwargs)
    else:
        raise ValueError("Unknown data context.")