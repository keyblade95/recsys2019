from scipy.sparse import save_npz
import data
import numpy as np
from tqdm import tqdm
import pandas as pd
import pickle
from utils.check_folder import check_folder
from preprocess_utils.create_dataset_tf_tanking import merge_features
from extract_features.actions_involving_impression_session import ActionsInvolvingImpressionSession
from extract_features.frenzy_factor_consecutive_steps import FrenzyFactorSession
from extract_features.global_clickout_popularity import GlobalClickoutPopularity
from extract_features.global_interactions_popularity import GlobalInteractionsPopularity
from extract_features.impression_features import ImpressionFeature
from extract_features.impression_position_session import ImpressionPositionSession
from extract_features.impression_price_info_session import ImpressionPriceInfoSession
from extract_features.label import ImpressionLabel
from extract_features.last_action_involving_impression import LastInteractionInvolvingImpression
from extract_features.mean_price_clickout import MeanPriceClickout
from extract_features.price_position_info_interactions import PricePositionInfoInteractedReferences
#from extract_features.session_actions_num_ref_diff_from_impressions import SessionActionNumRefDiffFromImpressions
from extract_features.session_device import SessionDevice
from extract_features.session_filters_active_when_clickout import SessionFilterActiveWhenClickout
from extract_features.session_length import SessionLength
from extract_features.session_sort_order_when_clickout import SessionSortOrderWhenClickout
from extract_features.time_from_last_action_before_clk import TimeFromLastActionBeforeClk
from extract_features.times_impression_appeared_in_clickouts_session import TimesImpressionAppearedInClickoutsSession
from extract_features.times_user_interacted_with_impression import TimesUserInteractedWithImpression
from extract_features.timing_from_last_interaction_impression import TimingFromLastInteractionImpression


def groups(users, sessions):
    au = users[0]
    ai = sessions[0]
    groups = []
    count = 1
    for j in range(len(users)):
        u = users[j]
        i = sessions[j]
        if u != au or i != ai:
            groups.append(count - 1)
            count = 1
            au = u
            ai = i
        count += 1
    groups.append(count - 1)
    return groups


def create_groups(df):
    users = df['user_id'].to_dense().values
    sessions = df['session_id'].to_dense().values
    print('data are ready')
    group = groups(list(users), list(sessions))
    return group


def create_dataset(mode, cluster):
    # training
    features_array = {
        'user_id_session_id_item_id': [ActionsInvolvingImpressionSession, ImpressionLabel, ImpressionPriceInfoSession,
                                       TimingFromLastInteractionImpression, TimesUserInteractedWithImpression,
                                       ImpressionPositionSession, LastInteractionInvolvingImpression,
                                       TimesImpressionAppearedInClickoutsSession],
        'user_id_session_id': [MeanPriceClickout, SessionLength, TimeFromLastActionBeforeClk,
                               FrenzyFactorSession, PricePositionInfoInteractedReferences,
                               SessionDevice, SessionSortOrderWhenClickout],
        'item_id': [GlobalInteractionsPopularity, GlobalClickoutPopularity]
    }

    train_df, test_df, target_indices_reordered = merge_features(mode, cluster, features_array)

    check_folder('dataset/preprocessed/{}/{}/xgboost/'.format(cluster, mode))

    X_train = train_df.drop(['user_id', 'session_id', 'item_id', 'label'], axis=1)
    X_train.to_csv('dataset/preprocessed/{}/{}/xgboost/X_train.csv'.format(cluster, mode), index=False)
    # X_train = X_train.astype(np.float64)
    # X_train = X_train.to_coo().tocsr()
    # save_npz(
    #     'dataset/preprocessed/{}/{}/xgboost/X_train'.format(cluster, mode), X_train)
    print('X_train saved')

    y_train = train_df[['label']]
    y_train.to_csv(
        'dataset/preprocessed/{}/{}/xgboost/y_train.csv'.format(cluster, mode), index=False)
    print('y_train saved')

    group = create_groups(train_df)
    np.save('dataset/preprocessed/{}/{}/xgboost/group'.format(cluster, mode), group)
    print('groups saved')

    print('train data completed')

    X_test = test_df.drop(['user_id', 'session_id', 'item_id', 'label'], axis=1)
    X_test.to_csv('dataset/preprocessed/{}/{}/xgboost/X_test.csv'.format(cluster, mode), index=False)
    print('X_test saved')


    np.save('dataset/preprocessed/{}/{}/xgboost/target_indices_reordered'.format(cluster, mode),
            target_indices_reordered)
    print('target indices reordered saved')

    print('test data completed')


if __name__ == "__main__":
    from utils.menu import mode_selection
    mode = mode_selection()
    cluster = 'no_cluster'
    create_dataset(mode, cluster)
