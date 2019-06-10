from extract_features.feature_base import FeatureBase
import data
import pandas as pd
from tqdm.auto import tqdm
import numpy as np
from preprocess_utils.last_clickout_indices import find
from preprocess_utils.last_clickout_indices import expand_impressions


class SessionNumClickouts(FeatureBase):

    """
    This feature says for each session the number of clickouts

    user_id | session_id | num_clickouts

    """

    def __init__(self, mode, cluster='no_cluster'):
        name = 'session_num_clickouts'
        super(SessionNumClickouts, self).__init__(
            name=name, mode=mode, cluster=cluster)

    def extract_feature(self):
        train = data.train_df(mode=self.mode, cluster=self.cluster)
        test = data.test_df(mode=self.mode, cluster=self.cluster)
        df = pd.concat([train, test])

        df_clk = df[df.action_type=='clickout item'][['user_id','session_id','timestamp','step','action_type']]
        feature = (
            df_clk.groupby(['user_id','session_id'])
            .size()
            .reset_index(name='num_clickouts')
        )

        return feature

if __name__ == '__main__':
    import utils.menu as menu

    mode = menu.mode_selection()
    cluster = menu.cluster_selection()

    c = SessionNumClickouts(mode, cluster)

    print('Creating {} for {} {}'.format(c.name, c.mode, c.cluster))
    c.save_feature()

    print(c.read_feature())
