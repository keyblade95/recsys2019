import sys
import os
sys.path.append(os.getcwd())

import data
import pandas as pd
import utils.sparsedf as sparsedf

import numpy as np
import scipy.sparse as sps
from sklearn.preprocessing import MultiLabelBinarizer
from keras.utils import to_categorical
from tqdm import tqdm

# from utils.df import scale_dataframe
# from sklearn.preprocessing import MinMaxScaler


# ======== PRE-PROCESSING ========= #

def save_accomodations_one_hot(accomodations_df, path):
    """ Save a sparse dataframe with columns: item_id  |  feature1 | feature2 | feature3 | feature4... """
    # one-hot encoding of the accomodations features
    item_ids = accomodations_df.item_id
    accomodations_df.properties = accomodations_df.properties.str.split('|')
    accomodations_df.properties = accomodations_df.properties.fillna('')

    mlb = MultiLabelBinarizer() #(sparse_output=True)
    attributes_df = mlb.fit_transform(accomodations_df.properties)
    #attributes_df = pd.SparseDataFrame(attributes_df, columns=mlb.classes_, default_fill_value=0)
    attributes_df = pd.DataFrame(attributes_df, columns=mlb.classes_)

    # re-add item_id column to get: item_id  |  one_hot_features[...]
    attributes_df = pd.concat([item_ids, attributes_df], axis=1)

    print('Saving one-hot accomodations...', end=' ', flush=True)
    attributes_df.to_csv(path, index=False)
    # with open('features1hot', 'w') as f:
    #     pickle.dump(features_columns, f)
    print('Done!')
    return attributes_df

def one_hot_df_column(df, column_label, classes, sparse=False):
    """ Substitute a dataframe column with its one-hot encoding derived columns """
    mlb = MultiLabelBinarizer(classes=classes, sparse_output=sparse)
    res = mlb.fit_transform(df[column_label].values.reshape(-1,1))
    
    if sparse:
        df[classes] = pd.SparseDataFrame(res, columns=mlb.classes_, dtype='Int8', index=df.index)
    else:
        for i,col in enumerate(mlb.classes_):
            df[col] = pd.Series(res[:,i], dtype='int8', index=df.index)
    return df.drop(column_label, axis=1)

def add_accomodations_features(df, path_to_save, logic='skip', row_indices=[]):
    """
    Add the features (one-hot) to the dataframe that match the 'reference' and save the resulting dataframe.
    It is possible to specify a list of rows to skip (logic='skip'), or to join only for some rows (logic='subset').
    Return the target columns and the one-hot columns that have been added to the dataframe
    """
    # save the references series and then set the reference to NaN to skip the join on that rows
    join_data = dict()
    join_data['backup_reference_series'] = df.reference.values.copy()
    if len(row_indices) > 0:
        if logic == 'skip':
            # set to NaN the rows to be skipped
            df.loc[row_indices, 'reference'] = np.nan
        if logic == 'subset':
            # set to NaN all rows, except for the specified rows
            backup_serie = df.loc[row_indices].reference.copy()
            df.reference = np.nan            
            df.loc[row_indices, 'reference'] = backup_serie

    # cast the reference column to Int64 removing the string values
    df.reference = pd.to_numeric(df.reference, errors='coerce') #.astype('Int64')

    # one-hot encoding of the accomodations features
    attributes_df = data.accomodations_one_hot()
    # accomodations features columns
    #features_columns = attributes_df.columns
    # with open(one_hot_accomodations_features_path, 'w') as f:
    #     pickle.dump(features_columns, f)

    #original_columns = set(df.columns)

    # add the 'no-reference' column
    #df['no_reference'] = (~df.reference.fillna('').str.isnumeric()) * 1
    
    # after_one_hot_columns = set(df.columns)
    # one_hot_columns = after_one_hot_columns.difference(original_columns)
    # one_hot_columns = list(one_hot_columns.union(set(features_columns)))
    
    def post_join(chunk_df, data):
        # reset the original references
        #chunk_df.loc[:,'reference'] = data['backup_reference_series'][data['$i1']:data['$i2']]
        return chunk_df.drop('reference', axis=1)
    
    sparsedf.left_join_in_chunks(df, attributes_df, left_on='reference', right_on=None, right_index=True,
                                post_join_fn=post_join, data=join_data, path_to_save=path_to_save)

    # print('Reloading the partial dataframe...', end=' ', flush=True)
    # df = sparsedf.read(path_to_save, sparse_cols=features_columns).set_index('orig_index')
    # reset the correct references from the backup
    #df.reference = backup_reference_series

    # return the features columns and the one-hot attributes
    #return df

def add_reference_labels(df, actiontype_col='clickout item', action_equals=1, classes_prefix='ref_',
                            num_classes=25, only_clickouts=False):
    """ Add the reference index in the impressions list as a new column for each clickout in the dataframe.
    For the clickout interactions, a 1 is placed in the column with name {classes_prefix}{reference index in impressions}.
    For the non-clickout interactions, 0s are placed in every columns with names {classes_prefix}{0...} if 
    only_clickouts is True, else set the label for all the interactions in the session
    """
    res_df = df.copy()
    tqdm.pandas()
    if only_clickouts:
        def set_class(row):
            if row[actiontype_col] == action_equals:
                try:
                    ref_class = row.impressions.split('|').index(row.reference)
                except ValueError:
                    ref_class = 0
                return ref_class
            else:
                return -1
    else:
        def set_class(group):
            clickouts = group[group[actiontype_col] == action_equals]
            if len(clickouts) > 0:
                last_clickout = clickouts.iloc[-1]
                try:
                    ref_class = last_clickout.impressions.split('|').index(last_clickout.reference)
                except ValueError:
                    ref_class = 0
                    #print(clickouts.iloc[[-1]].index)      # reference not in the impressions
                group['temp_ref_class'] = ref_class
            return group

    res_df['temp_ref_class'] = -1
    if only_clickouts:
        res_df['temp_ref_class'] = res_df.progress_apply(set_class, axis=1)
    else:
        res_df = res_df.groupby('session_id').progress_apply(set_class)
    # one-hot encode the classes
    ref_classes = ['{}nan'.format(classes_prefix)] + ['{}{}'.format(classes_prefix, i) for i in range(num_classes)]
    encoding = to_categorical(res_df['temp_ref_class']+1, num_classes=len(ref_classes), dtype='int8')
    # add the encoding columns, skipping the first one (ref_nan column)
    ref_classes = ref_classes[1:]
    for i,c in enumerate(ref_classes):
        res_df[c] = encoding[:,i+1]

    return res_df.drop('temp_ref_class', axis=1), ref_classes

def add_reference_binary_labels(df, actiontype_col='clickout item', action_equals=1, only_clickouts=False):
    """ Create a new column 'ref_class' containing 1 if the correct reference is the first in the impressions list,
    0 otherwise. If only_clickouts is True, set the label in each interaction of the sessions, otherwise set the label
    for all the interactions in the session.
    """
    res_df = df.copy()
    tqdm.pandas()
    if only_clickouts:
        def set_class(row):
            if row[actiontype_col] == action_equals:
                try:
                    ref_class = 1 if row.impressions.split('|').index(row.reference) == 0 else 0
                except ValueError:
                    ref_class = 0
                return ref_class
            else:
                return 0
    else:
        def set_class(group):
            clickouts = group[group[actiontype_col] == action_equals]
            if len(clickouts) > 0:
                last_clickout = clickouts.iloc[-1]
                try:
                    ref_class = 1 if last_clickout.impressions.split('|').index(last_clickout.reference) == 0 else 0
                except ValueError:
                    ref_class = 0
                    #print(clickouts.iloc[[-1]].index)      # reference not in the impressions
                group['ref_class'] = ref_class
            return group

    res_df['ref_class'] = 0
    if only_clickouts:
        res_df['ref_class'] = res_df.progress_apply(set_class, axis=1)
    else:
        res_df = res_df.groupby('session_id').progress_apply(set_class)
    
    return res_df.astype({'ref_class':'int8'})

def get_last_clickout(df, index_name=None, rename_index=None):
    """ Return a dataframe with the session_id as index and the reference of the last clickout of that session. """
    tqdm.pandas()
    def take_last_clickout(g, index_name, rename_index):
        clickouts = g[g.action_type == 'clickout item']
        if clickouts.shape[0] == 0:
            return None
        
        last_clickout_row = clickouts.iloc[-1]
        if index_name is None or rename_index is None:
            return pd.Series({'reference': last_clickout_row.reference})
        else:
            return pd.Series({rename_index: last_clickout_row[index_name], 'reference': last_clickout_row.reference})
    
    cols = ['session_id','action_type','reference']
    if index_name is not None:
        df = df.reset_index()
        cols.insert(0, index_name)

    df = df[cols].groupby('session_id').progress_apply(take_last_clickout, index_name=index_name, rename_index=rename_index)
    return df.dropna().astype(int)

def add_impressions_as_new_actions(df, new_rows_starting_index=99000000, drop_cols=['impressions','prices']):
    """
    Add dummy actions before each clickout to indicate each one of the available impressions.
    Prices are incorporated inside the new rows in a new column called 'impression_price'.
    Since this is the most expensive task of the creation process, a multicore implementation would allow to split
    the work between the cpu cores (but obviuosly not working!)
    """
    df['impression_price'] = 0     #np.nan
    clickout_rows = df[df.action_type == 'clickout item']
    print('Total clickout interactions found:', clickout_rows.shape[0], flush=True)

    # build a new empty dataframe containing the original one with additional rows used to append the new interactions
    columns = list(df.columns)
    # since we don't know exactly the tot rows to append, estimate it with an upper bound, later we discard the exceeding rows 
    rows_upper_bound = clickout_rows.shape[0] * 25
    # indices are expanded with a new series (starting from 'new_rows_starting_index')
    new_indices = np.concatenate([df.index.values, np.arange(new_rows_starting_index, new_rows_starting_index + rows_upper_bound)])
    res_df = pd.DataFrame(index=new_indices, columns=columns)
    # copy the original dataframe at the begininng
    res_df.iloc[0:df.shape[0]] = df.values
    # cache the column indices to access quickly at insertion time
    show_impr_col_index = columns.index('action_type')
    steps_col_index = columns.index('step')
    reference_col_index = columns.index('reference')
    price_col_index = columns.index('impression_price')
    
    j = new_rows_starting_index         # keep tracks of the inserted rows
    for _, row in tqdm(clickout_rows.iterrows()):
        # for each clickout interaction, create a group of row to write at the end of the resulting dataframe
        impressions = list(map(int, row.impressions.split('|')))
        imprs_count = len(impressions)
        prices = list(map(int, row.prices.split('|')))
        # repeat the clickout row as many times as the impressions count and set the action_type to 'show_impression'
        rows_to_set = np.tile(row.values, (imprs_count,1))
        rows_to_set[:,show_impr_col_index] = 'show_impression'
        # set the new series of reference, prices, intermediate time steps
        rows_to_set[:,reference_col_index] = impressions
        rows_to_set[:,price_col_index] = prices
        rows_to_set[:,steps_col_index] = np.linspace(row.step-1+1/imprs_count, row.step, imprs_count+1)[0:-1]
        # write the group of rows into the right location by index
        indices = np.arange(j, j+imprs_count)
        res_df.loc[indices] = rows_to_set

        j += imprs_count

    # drop the specified columns and discard the exceeding empty rows
    res_df = res_df.drop(drop_cols, axis=1).loc[0:j-1]
    return res_df.sort_values(['user_id','session_id','timestamp','step']), j

def pad_sessions(df, max_session_length):
    """ Pad/truncate each session to have the specified length (pad by adding a number of initial rows) """
    tqdm.pandas()

    def pad(g, max_length):
        # remove all interactions after the last clickout
        clickout_rows = g[g.action_type == 'clickout item']
        if clickout_rows.shape[0] > 0:
            index_of_last_clickout = clickout_rows.iloc[[-1]].index.values[0]
            g = g.loc[:index_of_last_clickout]
        
        grouplen = g.shape[0]
        if grouplen <= max_length:
            # pad with zeros
            array = np.zeros((max_length, g.shape[1]), dtype=object)
            # set index to -1 timestamp as the first one
            array[:,0] = -1
            # user_id and session_id are set equal to the ones for the current session
            array[:,1] = g.user_id.values[0]
            array[:,2] = g.session_id.values[0]
            # timestamp is set equal to the first of the sequence
            array[:,3] = g.timestamp.values[0]
            # the final part is written in place of the zeros
            array[-grouplen:] = g.values[-grouplen:]
        else:
            # truncate
            array = g.values[-max_length:]
        return pd.DataFrame(array, columns=g.columns)
    
    return df.reset_index().groupby('session_id').progress_apply(pad, max_length=max_session_length).set_index('index')

def sessions2tensor(df, drop_cols=[], return_index=False):
    """
    Build a tensor of shape (number_of_sessions, sessions_length, features_count).
    It can return also the indices of the tensor elements.
    """
    if len(drop_cols) > 0:
        sessions_values_indices_df = df.groupby('session_id').apply(lambda g: pd.Series({'tensor': g.drop(drop_cols, axis=1).values, 'indices': g.index.values}))
    else:
        sessions_values_indices_df = df.groupby('session_id').apply(lambda g: pd.Series({'tensor': g.values, 'indices': g.index.values}))
    
    #print(sessions_values_indices_df.shape)
    if return_index:
        return np.array(sessions_values_indices_df['tensor'].to_list()), np.array(sessions_values_indices_df['indices'].to_list())
    else:
        return np.array(sessions_values_indices_df['tensor'].to_list())




# ======== POST-PROCESSING ========= #

# def load_training_dataset_for_regression(mode):
#     """ Load the one-hot dataset and return X_train, Y_train """
#     path = f'dataset/preprocessed/{cluster}/{mode}'
#     X_path = os.path.join(path, 'X_train.csv')
#     Y_path = os.path.join(path, 'Y_train.csv')

#     X_train_df = pd.read_csv(X_path, index_col=0) #sparsedf.read(X_path, sparse_cols=X_sparsecols).set_index('orig_index')
#     Y_train_df = pd.read_csv(Y_path, index_col=0) #sparsedf.read(Y_path, sparse_cols=Y_sparsecols).set_index('orig_index')

#     #X_test_df = pd.read_csv(f'dataset/preprocessed/{cluster}/{mode}/X_test.csv').set_index('orig_index')

#     # turn the timestamp into the day of year
#     X_train_df.timestamp = pd.to_datetime(X_train_df.timestamp, unit='s')
#     X_train_df['dayofyear'] = X_train_df.timestamp.dt.dayofyear

#     cols_to_drop_in_X = ['user_id','session_id','timestamp','step','platform','city','current_filters']
#     cols_to_drop_in_Y = ['session_id','user_id','timestamp','step']
    
#     # scale the dataframe
#     #X_train_df = scale_dataframe(X_train_df, ['impression_price'])
#     scaler = MinMaxScaler()
#     X_train_df.loc[:,~X_train_df.columns.isin(cols_to_drop_in_X)] = scaler.fit_transform(
#         X_train_df.drop(cols_to_drop_in_X, axis=1).astype('float64').values)

#     # get the tensors and drop currently unused columns
#     X_train = sessions2tensor(X_train_df, drop_cols=cols_to_drop_in_X)
#     print('X_train:', X_train.shape)

#     Y_train = sessions2tensor(Y_train_df, drop_cols=cols_to_drop_in_Y)
#     print('Y_train:', Y_train.shape)

#     # X_test = sessions2tensor(X_test_df, drop_cols=['user_id','session_id','step','reference','platform','city','current_filters'], return_index=False)
#     # print('X_test:', X_test.shape)

#     # X_train.impression_price = X_train.impression_price.fillna(value=0)
#     # X_test.impression_price = X_test.impression_price.fillna(value=0)
    
#     return X_train, Y_train #, X_test


# def get_session_groups_indices_df(X_df, Y_df, cols_to_group=['user_id','session_id'], indices_col_name='intrctns_indices'):
#     """
#     Return a dataframe with columns 'user_id', 'session_id', 'intrctns_indices'. This is used to retrieve the
#     interaction indices from a particular session id of a user
#     """
#     return X_df.groupby(cols_to_group).apply(lambda r: pd.Series({indices_col_name: r.index.values})).reset_index()

