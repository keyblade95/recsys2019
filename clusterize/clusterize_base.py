from abc import abstractmethod
from abc import ABC
import os
import data
import numpy as np
from utils.check_folder import check_folder
import preprocess

class ClusterizeBase(ABC):

    def __init__(self):
        self.name = 'clusterbase'

        self.train_indices = []
        self.test_indices = []
        self.target_indices = []

    @abstractmethod
    def _fit(self):
        """
        save on self the following lists:
        (:,,) -> indices of base_split/full/train to be included in cluster full training set
        (,:,) -> indices of base_split/full/test  to be included in cluster full test set
        (,,:) -> indices of base_split/full/test  that represents clickouts to be predicted
        
        third argument is optional: one should specify it only in case wants to impose the clickouts
                                    to be predicted. otherwise those will be set automatically equal
                                    to the missing clickouts indicated by the 2nd argument 
        """
        pass
    
    def save(self):
        """
        makes use of fit to create the dataset for a specific cluster. in particular it take cares
        to create a folder at the same level of base_split with the specified name and the
        folders structure inside 
        """
        self._fit()

        full_df = data.full_df()

        # create cluster root folder
        path = f'dataset/preprocessed/{self.name}'
        check_folder(path)

        # create full and local folders
        full_path = os.path.join(path, 'full')
        local_path = os.path.join(path, 'local')
        small_path = os.path.join(path, 'small')
        check_folder(full_path)
        check_folder(local_path)
        check_folder(small_path)
        
        # create full files:    train_df.csv  -  test_df.csv  -  target_indices.npy
        test_full_df = full_df.loc[self.test_indices].to_csv(os.path.join(full_path, 'test.csv'))
        if len(self.target_indices) > 0:
            np.save(os.path.join(full_path, 'target_indices'), self.target_indices)
        else:
            trgt_indices = preprocess.get_target_indices(test_full_df)
            np.save(os.path.join(full_path, 'target_indices'), trgt_indices)
        del test_full_df

        train_full_df = full_df.loc[self.train_indices]
        train_full_df.to_csv(os.path.join(full_path, 'train.csv'))

        # create local files:    train_df.csv  -  test_df.csv  -  target_indices.npy
        preprocess.split(train_full_df, local_path, perc_train=80)

        # create small files:    train_df.csv  -  test_df.csv  -  target_indices.npy
        small_df = preprocess.get_small_dataset(train_full_df)
        preprocess.split(small_df, small_path, perc_train=80)
        