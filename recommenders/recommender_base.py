from abc import abstractmethod
from abc import ABC
import data
import numpy as np
from tqdm import tqdm
import out


class RecommenderBase(ABC):
    """ Defines the interface that all recommendations models expose """

    def __init__(self, mode='full', cluster='no_cluster', name='recommenderbase'):
        """
        init should have on its firm the params of the algorithm
        """
        self.name = name
        self.mode = mode
        self.cluster = cluster

    @abstractmethod
    def fit(self):
        """
        Fit the model on the data. Inherited class should extend this method in the appropriate way.
        """
        pass

    @abstractmethod
    def recommend_batch(self):
        """
        Returns a list of recommendations in the format
        [(session_idx_0, [acc_1, acc2, acc3, ...]), 
         (session_idx_1, [acc_1, acc2, acc3, ...]), ...]
        """
        pass

    @abstractmethod
    def get_scores_batch(self):
        """
        returns a list of recommendations in the format
        [(session_idx_0, [acc_1, acc2, acc3, ...], [sco_1, sco2, sco3, ...]),
         (session_idx_0, [acc_1, acc2, acc3, ...], [sco_1, sco2, sco3, ...]), ...]
        """
        pass




    def run(self):
        """
        Handle all the operations needed to run this model a single time.
        In particular, performs the fit and get the recommendations.
        Then, it can either export the recommendations or not
        """
        export = False
        print('running {}'.format(self.name))
        if self.mode == 'full':
            export = True
            print("I gonna fit the model, recommend the accomodations, and save the submission")
        else:
            print("I gonna fit the model and recommend the accomodations")

        self.fit()
        recommendations = self.recommend_batch()
        if export:
            out.create_sub(recommendations, mode=self.mode, submission_name=self.name)

    def evaluate(self):
        """
        Validate the model on local data
        """
        assert self.mode == 'local' or self.mode == 'small'

        print('\nvalidating {}'.format(self.name))
        self.fit()
        recommendations = self.recommend_batch()
        print('recommendations created')
        return self.compute_MRR(recommendations)

    def compute_MRR(self, predictions):
        """
        compute the MRR mean reciprocal rank of some predictions
        it uses the mode parameter to know which handle to retrieve to compute the score

        :param mode: 'local' or 'small' say which train has been used
        :param predictions: session_id, ordered impressions_list
        :param verboose: if True print the MRR
        :return: MRR of the given predictions
        """
        assert (self.mode == 'local' or self.mode == 'small')

        full_df = data.full_df()

        target_indices, recs = zip(*predictions)
        target_indices = list(target_indices)
        correct_clickouts = full_df.loc[target_indices].reference.values
        len_rec = len(recs)
        
        RR = 0
        for i in range(len_rec):
            correct_clickout = int(correct_clickouts[i])
            if correct_clickout in predictions[i][1]:
                rank_pos = recs[i].index(correct_clickout) +1
                if rank_pos <= 25:
                    RR += 1 / rank_pos
        
        MRR = RR / len_rec
        print(f'MRR: {MRR}')

        return MRR

    def get_params(self):
        """
        returns the dictionaries used for the bayesian search validation
        the two dictionaries have to be implemented by each recommenders in the init!

        """
        if (self.fixed_params_dict is None) or (self.hyperparameters_dict is None):
            print('dictionaries of the parameters have not been set on the recommender!!')
            exit(0)
        return self.fixed_params_dict, self.hyperparameters_dict

