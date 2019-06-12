import sys
import os
sys.path.append(os.getcwd())

import numpy as np
import pandas as pd
import copy
from utils.check_folder import check_folder
from sklearn.model_selection import KFold
from joblib import Parallel, delayed


class KFoldScorer(object):
    """
    Get the scores for the dataset by fitting each model in K-fold (except one) and
    computing the scores for the left-out fold.
    The underlying model should implement the following methods:
    - fit_cv(x, y, x_val, y_val, **params)
    - get_scores_cv(x)      : must return a dataframe with columns [ user_id | session_id | item_id | score ]
    """

    def __init__(self, model_class, init_params:dict, k:int):
        self.model_class = model_class
        self.init_params = init_params
        self.k = k
        self.scores = []
    
    # train a single model on a fold
    def _fit_model(self, x, y, x_val, y_val, fit_params, pool_id=0):
        print(f'start {pool_id}')
        model = self.model_class(**self.init_params)
        assert hasattr(model, 'fit_cv') and hasattr(model, 'get_scores_cv'), \
            'Model must implement methods: fit_cv, get_scores_cv'
        model.fit_cv(x, y, x_val, y_val, **fit_params)
        print(f'fit end {pool_id}')
        # compute scores
        return model.get_scores_cv(x_val)

    def fit_predict(self, dataset, fit_params={}, n_jobs=-1, save_folder='scores/') -> pd.DataFrame:
        """ Fit and compute the scores for each fold.
        dataset (object):   inheriting from utils.dataset.DatasetBase
        fit_params (dict):  params to fit the model
        n_jobs (int):       maximum number of concurrently running jobs, -1 to use all CPUs
        save_folder (str):  folder where to save the scores
        """
        assert hasattr(dataset, 'load_Xtrain') and hasattr(dataset, 'load_Ytrain') and hasattr(dataset, 'load_Xtest'), \
            'Dataset object must implement methods: load_Xtrain, load_Ytrain, load_Xtest'
        
        X_train, Y_train, X_test = dataset.load_Xtrain(), dataset.load_Ytrain(), dataset.load_Xtest()
        
        # kfold
        kf = KFold(n_splits=self.k)
        
        # fit in each fold
        self.scores = Parallel(backend='multiprocessing', n_jobs=n_jobs)(delayed(self._fit_model)
                                (
                                    X_train[train_indices], Y_train[train_indices], 
                                    X_train[test_indices], Y_train[test_indices], 
                                    fit_params, idx
                                ) for idx,(train_indices,test_indices) in enumerate(kf.split(X_train)) )
        
        # fit in all the train and get scores for test
        print('fit whole train')
        model = self.model_class(**self.init_params)
        model.fit_cv(X_train, Y_train, None, None, **fit_params)
        print('end fit whole train')
        scores_test = model.get_scores_cv(X_test)
        self.scores.append( scores_test )
        
        self.scores = pd.concat(self.scores)

        # save scores
        if save_folder is not None:
            check_folder(save_folder)
            filepath = os.path.join(save_folder, model.name, '.csv')
            print('Saving scores to', filepath, end=' ', flush=True)
            self.scores.to_csv(filepath, index=False)
            print('Done!', end=' ', flush=True)
        
        return self.scores
        

if __name__ == "__main__":
    from utils.dataset import DatasetScoresClassification
    from recommenders.recurrent.RNNClassificationRecommender import RNNClassificationRecommender

    dataset = DatasetScoresClassification(f'dataset/preprocessed/cluster_recurrent/small/dataset_classification_p6')

    init_params = {
        'dataset': dataset,
        'input_shape': (6,168),
        'cell_type': 'gru',
        'num_recurrent_layers': 2,
        'num_recurrent_units': 64,
        'num_dense_layers': 2
    }
    fit_params = {'epochs': 1, 'early_stopping_patience': 4}

    kfscorer = KFoldScorer(model_class=RNNClassificationRecommender, init_params=init_params, k=2)

    kfscorer.fit_predict(dataset, fit_params=fit_params)