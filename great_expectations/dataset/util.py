# Utility methods for dealing with Dataset objects

from __future__ import division

from six import string_types, integer_types

import numpy as np
from scipy import stats
import pandas as pd
import warnings
import sys
import copy
import datetime

from functools import wraps


def parse_result_format(result_format):
    """This is a simple helper utility that can be used to parse a string result_format into the dict format used
    internally by great_expectations. It is not necessary but allows shorthand for result_format in cases where
    there is no need to specify a custom partial_unexpected_count."""
    if isinstance(result_format, string_types):
        result_format = {
            'result_format': result_format,
            'partial_unexpected_count': 20
        }
    else:
        if 'partial_unexpected_count' not in result_format:
            result_format['partial_unexpected_count'] = 20

    return result_format

class DotDict(dict):
    """dot.notation access to dictionary attributes"""

    def __getattr__(self, attr):
        return self.get(attr)

    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__

    def __dir__(self):
        return self.keys()

    #Cargo-cultishly copied from: https://github.com/spindlelabs/pyes/commit/d2076b385c38d6d00cebfe0df7b0d1ba8df934bc
    def __deepcopy__(self, memo):
        return DotDict([(copy.deepcopy(k, memo), copy.deepcopy(v, memo)) for k, v in self.items()])


"""Docstring inheriting descriptor. Note that this is not a docstring so that this is not added to @DocInherit-\
decorated functions' hybrid docstrings.

Usage::

    class Foo(object):
        def foo(self):
            "Frobber"
            pass

    class Bar(Foo):
        @doc_inherit
        def foo(self):
            pass

    Now, Bar.foo.__doc__ == Bar().foo.__doc__ == Foo.foo.__doc__ == "Frobber"

    Original implementation cribbed from:
    https://stackoverflow.com/questions/2025562/inherit-docstrings-in-python-class-inheritance,
    following a discussion on comp.lang.python that resulted in:
    http://code.activestate.com/recipes/576862/. Unfortunately, the
    original authors did not anticipate deep inheritance hierarchies, and
    we ran into a recursion issue when implementing custom subclasses of
    PandasDataset:
    https://github.com/great-expectations/great_expectations/issues/177.

    Our new homegrown implementation directly searches the MRO, instead
    of relying on super, and concatenates documentation together.
"""
class DocInherit(object):

    def __init__(self, mthd):
        self.mthd = mthd
        self.name = mthd.__name__
        self.mthd_doc = mthd.__doc__

    def __get__(self, obj, cls):
        doc = self.mthd_doc if self.mthd_doc is not None else ''

        for parent in cls.mro():
            if self.name not in parent.__dict__:
                continue
            if parent.__dict__[self.name].__doc__ is not None:
                doc = doc + '\n' + parent.__dict__[self.name].__doc__

        @wraps(self.mthd, assigned=('__name__', '__module__'))
        def f(*args, **kwargs):
            return self.mthd(obj, *args, **kwargs)

        f.__doc__ = doc
        return f


def recursively_convert_to_json_serializable(test_obj):
    """
    Helper function to convert a dict object to one that is serializable

    Args:
        test_obj: an object to attempt to convert a corresponding json-serializable object

    Returns:
        (dict) A converted test_object

    Warning:
        test_obj may also be converted in place.

    """
    # Validate that all aruguments are of approved types, coerce if it's easy, else exception
    if isinstance(test_obj, (string_types, integer_types, float, bool)):
        # No problem to encode json
        return test_obj

    elif test_obj is None:
        # No problem to encode json
        return test_obj

    elif isinstance(test_obj, dict):
        new_dict = {}
        for key in test_obj:
            new_dict[key] = recursively_convert_to_json_serializable(test_obj[key])

        return new_dict

    elif isinstance(test_obj, (list, tuple, set)):
        new_list = []
        for val in test_obj:
            new_list.append(recursively_convert_to_json_serializable(val))

        return new_list

    elif isinstance(test_obj, (np.ndarray, pd.Index)):
        #test_obj[key] = test_obj[key].tolist()
        ## If we have an array or index, convert it first to a list--causing coercion to float--and then round
        ## to the number of digits for which the string representation will equal the float representation
        return [recursively_convert_to_json_serializable(x) for x in test_obj.tolist()]

    elif isinstance(test_obj, np.int64):
        return int(test_obj)

    elif isinstance(test_obj, np.float64):
        return float(round(test_obj, sys.float_info.dig))

    elif isinstance(test_obj, (datetime.datetime, datetime.date)):
        return str(test_obj)

    else:
        raise TypeError('%s is of type %s which cannot be serialized.' % (str(test_obj), type(test_obj).__name__))


def is_valid_partition_object(partition_object):
    """Tests whether a given object is a valid continuous or categorical partition object.
    :param partition_object: The partition_object to evaluate
    :return: Boolean
    """
    if is_valid_continuous_partition_object(partition_object) or is_valid_categorical_partition_object(partition_object):
        return True
    return False


def is_valid_categorical_partition_object(partition_object):
    """Tests whether a given object is a valid categorical partition object.
    :param partition_object: The partition_object to evaluate
    :return: Boolean
    """
    if partition_object is None or ("weights" not in partition_object) or ("values" not in partition_object):
        return False
    # Expect the same number of values as weights; weights should sum to one
    if len(partition_object['values']) == len(partition_object['weights']) and \
            np.allclose(np.sum(partition_object['weights']), 1):
        return True
    return False


def is_valid_continuous_partition_object(partition_object):
    """Tests whether a given object is a valid continuous partition object.
    :param partition_object: The partition_object to evaluate
    :return: Boolean
    """
    if (partition_object is None) or ("weights" not in partition_object) or ("bins" not in partition_object):
        return False
    # Expect one more bin edge than weight; all bin edges should be monotonically increasing; weights should sum to one
    if (len(partition_object['bins']) == (len(partition_object['weights']) + 1)) and \
            np.all(np.diff(partition_object['bins']) > 0) and \
            np.allclose(np.sum(partition_object['weights']), 1):
        return True
    return False


def categorical_partition_data(data):
    """Convenience method for creating weights from categorical data.
    
    Args:
        data (list-like): The data from which to construct the estimate.
    
    Returns:
        A new partition object::

            {
                "partition": (list) The categorical values present in the data
                "weights": (list) The weights of the values in the partition.
            }
    """

    # Make dropna explicit (even though it defaults to true)
    series = pd.Series(data)
    value_counts = series.value_counts(dropna=True)

    # Compute weights using denominator only of nonnull values
    null_indexes = series.isnull()
    nonnull_count = (null_indexes == False).sum()

    weights = value_counts.values / nonnull_count
    return {
        "values": value_counts.index.tolist(),
        "weights": weights
    }


def kde_partition_data(data, estimate_tails=True):
    """Convenience method for building a partition and weights using a gaussian Kernel Density Estimate and default bandwidth.

    Args:
        data (list-like): The data from which to construct the estimate
        estimate_tails (bool): Whether to estimate the tails of the distribution to keep the partition object finite

    Returns:
        A new partition_object::

        {
            "partition": (list) The endpoints of the partial partition of reals,
            "weights": (list) The densities of the bins implied by the partition.
        }
    """
    kde = stats.kde.gaussian_kde(data)
    evaluation_bins = np.linspace(start=np.min(data) - (kde.covariance_factor() / 2),
                                  stop=np.max(data) + (kde.covariance_factor() / 2),
                                  num=np.floor(((np.max(data) - np.min(data)) / kde.covariance_factor()) + 1 ).astype(int))
    cdf_vals = [kde.integrate_box_1d(-np.inf, x) for x in evaluation_bins]
    evaluation_weights = np.diff(cdf_vals)

    if estimate_tails:
        bins = np.concatenate(([np.min(data) - (1.5 * kde.covariance_factor())],
                               evaluation_bins,
                               [np.max(data) + (1.5 * kde.covariance_factor())]))
    else:
        bins = np.concatenate(([-np.inf], evaluation_bins, [np.inf]))

    weights = np.concatenate(([cdf_vals[0]], evaluation_weights, [1 - cdf_vals[-1]]))

    return {
        "bins": bins,
        "weights": weights
    }


def partition_data(data, bins='auto', n_bins=10):
    warnings.warn("partition_data is deprecated and will be removed. Use either continuous_partition_data or \
                    categorical_partition_data instead.", DeprecationWarning)
    return continuous_partition_data(data, bins, n_bins)


def continuous_partition_data(data, bins='auto', n_bins=10):
    """Convenience method for building a partition object on continuous data

    Args:
        data (list-like): The data from which to construct the estimate.
        bins (string): One of 'uniform' (for uniformly spaced bins), 'ntile' (for percentile-spaced bins), or 'auto' (for automatically spaced bins)
        n_bins (int): Ignored if bins is auto.

    Returns:
        A new partition_object::

        {
            "bins": (list) The endpoints of the partial partition of reals,
            "weights": (list) The densities of the bins implied by the partition.
        }
    """
    if bins == 'uniform':
        bins = np.linspace(start=np.min(data), stop=np.max(data), num = n_bins+1)
    elif bins =='ntile':
        bins = np.percentile(data, np.linspace(start=0, stop=100, num = n_bins+1))
    elif bins != 'auto':
        raise ValueError("Invalid parameter for bins argument")

    hist, bin_edges = np.histogram(data, bins, density=False)

    return {
        "bins": bin_edges,
        "weights": hist / len(data)
    }
