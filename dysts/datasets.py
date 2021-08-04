import json
import warnings
import numpy as np
import os
import pkg_resources

from .utils import *
import pandas as pd

class TimeSeriesDataset:
    """A data structure for handling time series. Reads and writes from JSON
    
    Assumes that all time series have the same number of timepoints. In the case
    of multivariate series with different numbers of features / dimensions, pads the
    missing dimensionality
    """
    def __init__(self, datapath=None):
        if not datapath:
            pass
        else:
            with open(datapath, "r") as file:
                self.dataset = json.load(file)
        
        self.rank = np.max(np.array([len(np.squeeze(np.array(self.dataset[item]["values"])).shape) for item in self.dataset]))
        self.is_multivariate = self.rank > 1
        
        if self.is_multivariate:
            self.max_d = np.max([np.array(self.dataset[item]["values"]).shape[-1] for item in self.dataset])

        for key in self.dataset:
            self.dataset[key]["values"] = np.array(self.dataset[key]["values"])
        self.names = np.array(list(self.dataset.keys()))

    def get_rowvalues(self, key):
        """Retrieve the value of a field from each row"""
        return np.array([self.dataset[item][key] for item in self.dataset])
        
    def __getitem__(self, key):
        return self.dataset[key]
    
    def __setitem__(self, key, val):
        self.dataset[key] = val
        
    def trim_series(self, start_val, stop_val):
        """
        Trims a time series in-place. This is not reversible without re-initializing
        """
        for key in self.dataset:
            self.dataset[key]["values"] = self.dataset[key]["values"][start_val:stop_val]
            self.dataset[key]["time"] = self.dataset[key]["time"][start_val:stop_val]
            
        
    def to_pandas(self, standardize=True, filling="constant"):
        """
        data (dict): A dictionary with index given by top-level keys
        
        Args:
            standardize (bool): whether to standardize each dataset before flattening
            filling (str): For multivariate time series of varying demensionality, values to pad 
                in empty columns.
        Returns:
            data_pd (pd.DataFrame): a 2D dataset consisting of indexed time series
        """
        data = self.dataset
        all_names = self.names
        all_times = np.vstack([data[item]["time"] for item in data])
        
#         all_values = np.vstack([data[item]["values"] for item in data])
        all_values = self.to_array(standardize=standardize)
        #self.max_d
        
        
        if self.is_multivariate:
            all_indices = (np.arange(all_times.shape[0])[:, None] * np.ones(all_times.shape[1])[None, :]).astype(int)
            all_values = np.squeeze(np.reshape(all_values, (-1, self.max_d)))
            all_indices, all_times = [np.reshape(item, (-1, 1)) for item in (all_indices, all_times)]
            all_data = np.hstack([all_indices, all_times, all_values]).T
            column_names = ["id", "time"] + [f"values_{i}" for i in range(self.max_d)]
        else:
            all_indices = (np.arange(all_times.shape[0])[:, None] * np.ones(all_times.shape[1])[None, :]).astype(int)
            all_data = np.vstack([np.ravel(item) for item in (all_indices, all_times, all_values)])
            column_names = ["id", "time", "values"]
        
        all_names = all_names[all_indices]
        data_pd = pd.DataFrame(all_data.T, columns=column_names, index=np.ravel(all_names))
        return data_pd
    
    def to_array(self, standardize=False):
        """
        Return the values of a time series as a matrix of shape (B, T, D) or (B, T)
        """
        data = self.dataset
        #all_values = np.vstack([data[item]["values"].T for item in data])
        all_values = np.squeeze(np.dstack([pad_axis(np.array(data[key]["values"]), 10, axis=-1).T for key in data]).T)
        if standardize:
            scale = np.std(all_values, axis=1, keepdims=True)
            scale[scale == 0] = 1
            all_values = (all_values - np.mean(all_values, axis=1, keepdims=True)) / scale
        return all_values
    
    def dump(self, path):
        with open(path, 'w') as file:
            json.dump(self.dataset, file, indent=4)  

from tsfresh import extract_features
from tsfresh import select_features
from tsfresh.utilities.dataframe_functions import impute
def featurize_timeseries(dataset):
    """
    Extract features from a TimeSeriesDataset
    """
    all_datasets = dataset.to_pandas(standardize=True)
    names = np.unique(dataset.to_pandas().index.to_list())
    extracted_features = extract_features(all_datasets, column_id="id", column_sort="time")
    extracted_features = extracted_features.dropna(axis=1) # drop nans
    extracted_features = extracted_features.loc[:, extracted_features.std() > 0.0] # drop nonvarying
    extracted_features -= extracted_features.mean() # subtract featurewise mean
    extracted_features = extracted_features.set_index(names)
    return extracted_features
    

def load_file(filename):
    """Locate and import from the module data directory"""
    base_path = pkg_resources.resource_filename('dysts', 'data')
    data_path = os.path.join(base_path, filename)
    dataset = TimeSeriesDataset(data_path)
    return dataset

# def load_continuous(subsets="train", univariate=True, granularity="fine"):
#     """
#     Load dynamics from continuous dynamical systems
    
#     Args:
#         subsets ("train" | "val" | "test" | "test_val"): Which dataset to draw.
#         univariate (bool): Whether to use one coordinate, or all for each system.
#         granularity ("course" | "fine"): Whether to use fine or coarsely-spaced samples
    
#     Returns:
#         dataset (TimeSeriesDataset): A collection of time series dataset
#     """
#     period = {"train": "10", "test": "2", "val": "2"}[subsets]
#     granval = {"coarse": "15", "fine": "100"}[granularity]
#     split_point = 5/6*period
#     # self.trim_series(split_point, -1)
#     if univariate:
#         dataset = load_file(f"{subsets}_univariate__pts_per_period_{granval}__periods_{period}.json")
#     else:
#         dataset = load_file(f"{subsets}_multivariate__pts_per_period_{granval}__periods_{period}.json")
#     return dataset

def load_dataset_sr(subsets="train", univariate=True, granularity="fine", data_format="object", **kwargs):
    """
    Load a datasets for symbolic regression
    """
    dataset = load_file("benchmarks/resources/symb_train_test_data.json")
    


def load_dataset(subsets="train", univariate=True, granularity="fine", data_format="object", **kwargs):
    """
    Load dynamics from continuous dynamical systems. 
    
    Args:
        subsets ("train" | "train_val" | "test" | "test_val" | "all"): Which dataset to draw.
            Train and train val correspond to the same time series split 5/6 of the way through,
            while "test" and "test_val" both represent a trajectory emanating from a different
            initial condition, split 5/6 of the way though.
        univariate (bool): Whether to use one coordinate, or all for each system.
        granularity ("course" | "fine"): Whether to use fine or coarsely-spaced samples
        data_format ("object" | "numpy" | "pandas"): The format to return
        kwargs (dict): keyword arguments passed to the data formatter
    
    Returns:
        dataset (TimeSeriesDataset): A collection of time series datasets
    """
    period = 12
    granval = {"coarse": 15, "fine": 100}[granularity]
    
    dataset_name = subsets.split("_")[0]
    
    if univariate:
        dataset = load_file(f"{dataset_name}_univariate__pts_per_period_{granval}__periods_{period}.json")
    else:
        dataset = load_file(f"{dataset_name}_multivariate__pts_per_period_{granval}__periods_{period}.json")
    
    split_point = int(5/6 * period) * granval
    if subsets == "train":
        dataset.trim_series(0, split_point)
    if subsets == "test":
        dataset.trim_series(0, split_point)
    if "val" in subsets:
        dataset.trim_series(split_point, -1)
        
    if data_format == "object":
        return dataset
    if data_format == "pandas":
        return dataset.to_pandas(**kwargs)
    if data_format == "numpy":
        return dataset.to_array(**kwargs)
    else:
        raise ValueError("Return format not recognized.")
        return None

def load_discrete(subsets="all"):
    """Load dynamics from discrete dynamical systems
    """
    dataset = load_file("dataset_univariate__pts_per_period_100__periods_10.json")
    return dataset

def make_dataset(random_state=None):
    pass
