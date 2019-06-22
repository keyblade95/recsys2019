import pandas as pd
import data
from tqdm import tqdm
from random import randint
import os
from shutil import copyfile, rmtree
from preprocess_utils.last_clickout_indices import find as find_last_clickout_indices
from utils import menu

cluster_name = "supersampling"
base_cluster = "no_cluster"
path = "dataset/preprocessed/{}".format(cluster_name)
base_path = "dataset/preprocessed/{}".format(base_cluster)

def already_existing():
    return os.path.isdir(path)

def get_class_to_sessions_dict(train):
    idxs = find_last_clickout_indices(train)
    train = train.loc[idxs]
    class_to_sessions = dict()
    for i in range(25):
        class_to_sessions[i] = list()
    for t in tqdm(zip(train.session_id, train.reference, train.impressions)):
        imps = list(map(int, t[2].split("|")))
        ref = int(t[1])
        if ref in imps:
            idx = imps.index(ref)
            class_to_sessions[idx] += [t[0]]
    return class_to_sessions

def get_session_to_indices_dict(train):
    session_to_indices = dict()
    start = 0
    end = 0
    train = train.drop_duplicates("session_id", keep="first")
    current_session = train.loc[0].session_id
    train = train.loc[1:]
    for t in tqdm(zip(train.index, train.session_id)):
        end = t[0] - 1
        session_to_indices[current_session] = [start, end]
        start = t[0]
        current_session = t[1]
    session_to_indices[current_session] = [start, len(train) - 1]
    return session_to_indices

def resample_session(class_to_sessions, train):
    temp = pd.DataFrame(columns=list(train))
    del class_to_sessions[0]
    selected_sessions = dict()
    for k, v in class_to_sessions.items():
        l = len(v)
        for i in range(l):
            x = v[randint(0, l - 1)]
            if x not in selected_sessions:
                selected_sessions[x] = 0
            selected_sessions[x] += 1
    return selected_sessions

def duplicate_sessions(sessions, train, session_to_indices):
    new = pd.DataFrame()
    while len(sessions) > 0:
        indices = list()
        mock_ids = list()
        for k, v in tqdm(sessions.items()):
            sessions[k] = v - 1
            idxs = session_to_indices[k]
            for x in range(idxs[0], idxs[1] + 1):
                indices.append(x)
                mock_ids.append("mock" + str(idxs[0]) + "_" + str(sessions[k]))
        sessions = {key:val for key, val in sessions.items() if val != 0}
        temp = train.loc[indices]
        temp["user_id"] = mock_ids
        temp["session_id"] = mock_ids
        new = pd.concat([temp, new])
    return new.reset_index(drop=True)

def supersampling(mode):
    print("Supersampling for mode: {}".format(mode))
    train = data.train_df(mode)
    class_to_sessions = get_class_to_sessions_dict(train)
    session_to_indices = get_session_to_indices_dict(train)
    sessions_to_be_resapmled = resample_session(class_to_sessions.copy(), train)
    new = duplicate_sessions(sessions_to_be_resapmled.copy(), train, session_to_indices)
    new = pd.concat([train, new])
    train_len = len(new)
    test = data.test_df(mode)
    new = pd.concat([new, test])
    new.reset_index(inplace=True, drop=True)
    print("Supersampling ended for mode={}, saving df".format(mode))
    new_train = new.loc[:train_len]
    new_test = new.loc[train_len:]
    new_train.to_csv(path + "/" + mode + "/train.csv", index=True)
    new_test.to_csv(path + "/" + mode + "/train.csv", index=True)

if __name__ == '__main__':
    if already_existing():
        answer = menu.yesno_choice(title='Another supersampling detected, do you want to recreate it?',
                                       callback_yes=lambda: True, callback_no=lambda: False)
        if answer:
            rmtree(path)
        else:
            exit(0)
    os.mkdir(path)
    modes = ["small", "local", "full"]
    for m in modes:
        os.mkdir(path + "/" + m)
        supersampling(m)

