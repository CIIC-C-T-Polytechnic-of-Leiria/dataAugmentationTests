#!pip install pytorch-tabnet wget
from pytorch_tabnet.tab_model import TabNetClassifier
import torch
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
from sklearn.metrics import precision_score
from sklearn.metrics import recall_score
from sklearn.metrics import roc_auc_score
from sklearn.metrics import f1_score
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
from sklearn.utils import shuffle
from sklearn import metrics
from sklearn import tree
from xgboost import plot_tree
import pandas as pd
import numpy as np
import os
import wget
from pathlib import Path
import shutil
import gzip
import joblib
from xgboost import XGBClassifier
from mlciic import functions
from mlciic import metrics as met
from matplotlib import pyplot as plt

random_state=42
np.random.seed(random_state)

def checkFields(row):
    return np.sum(row == 1) == 1

def applyVerification(df, lst):
    result = np.apply_along_axis(checkFields, 1, df[lst].values)
    counts = np.bincount(result.astype(int))
    #print("Number of True values: ", counts[1])
    #print("Number of False values: ", counts[0])
    # Remove rows with False values
    df_filtered = df[result]

    return df_filtered


df_train = pd.read_csv('../../../data/EdgeIIot_train_dummies.csv', low_memory=False)
df_test = pd.read_csv('../../../data/EdgeIIot_test_dummies.csv', low_memory=False)

functions.display_information_dataframe(df_train,showCategoricals = True, showDetailsOnCategorical = True, showFullDetails = True)

#print(df_train["Attack_type"].value_counts())

df_train.drop(["Attack_label"], axis=1, inplace=True)
df_test.drop(["Attack_label"], axis=1, inplace=True)

features = [ col for col in df_train.columns if col not in ["Attack_label"]+["Attack_type"]] 


#for the SMOTE part, so it can fit in 16gb of RAM
df_before = df_train
df_attacks = df_train[df_train["Attack_type"] != "Normal"]

df_normal = df_train[df_train["Attack_type"] == "Normal"]
df_normal = shuffle(df_normal)
df_normal = df_normal[:100000]
df_train = pd.concat([df_attacks,df_normal])
df_train = shuffle(df_train)


#Encoding
le = LabelEncoder()
le.fit(df_train["Attack_type"].values)

n_total = len(df_train)
test_indices, valid_indices = train_test_split(range(n_total), test_size=0.2, random_state=random_state)

X_train = df_train[features].values[test_indices]
y_train = df_train["Attack_type"].values[test_indices]
y_train = le.transform(y_train)

X_valid = df_train[features].values[valid_indices]
y_valid = df_train["Attack_type"].values[valid_indices]
y_valid = le.transform(y_valid)

X_test = df_test[features].values
y_test = df_test["Attack_type"].values
y_test = le.transform(y_test)

standScaler = StandardScaler()
model_norm = standScaler.fit(X_train)

#FAZER SMOTE AQUI
sm = SMOTE(random_state=random_state,n_jobs=-1)
X_train, y_train = sm.fit_resample(X_train, y_train)

df_test_After = pd.DataFrame(X_train,columns=features)
df_test_After["Attack_type"] = y_train

lst = ['http.request.method_0', 'http.request.method_1', 'http.request.method_2', 'http.request.method_3', 'http.request.method_4', 'http.request.method_5', 'http.request.method_6', 'http.request.method_7', 'http.request.method_8']

df_new = applyVerification(df_test_After, lst)

lst = ['http.referer_0', 'http.referer_1', 'http.referer_2', 'http.referer_3', 'http.referer_4']

df_new = applyVerification(df_test_After, lst)

lst = ['http.request.version_0', 'http.request.version_1', 'http.request.version_2', 'http.request.version_3', 'http.request.version_4','http.request.version_5','http.request.version_6','http.request.version_7','http.request.version_8','http.request.version_9','http.request.version_10','http.request.version_11','http.request.version_12']

df_new = applyVerification(df_test_After, lst)

lst = ['dns.qry.name.len_0', 'dns.qry.name.len_1', 'dns.qry.name.len_2', 'dns.qry.name.len_3', 'dns.qry.name.len_4', 'dns.qry.name.len_5', 'dns.qry.name.len_6', 'dns.qry.name.len_7', 'dns.qry.name.len_8']

df_new = applyVerification(df_test_After, lst)

lst = ['mqtt.conack.flags_0', 'mqtt.conack.flags_1', 'mqtt.conack.flags_2', 'mqtt.conack.flags_3', 'mqtt.conack.flags_4','mqtt.conack.flags_5','mqtt.conack.flags_6','mqtt.conack.flags_7','mqtt.conack.flags_8','mqtt.conack.flags_9','mqtt.conack.flags_10','mqtt.conack.flags_11','mqtt.conack.flags_12']

df_new = applyVerification(df_test_After, lst)

lst = ['mqtt.protoname_0', 'mqtt.protoname_1', 'mqtt.protoname_2']

df_new = applyVerification(df_test_After, lst)

lst = ['mqtt.topic_0', 'mqtt.topic_1', 'mqtt.topic_2']

df_new = applyVerification(df_test_After, lst)

X_train = df_new[features].values
y_train = df_new["Attack_type"].values

X_train = model_norm.transform(X_train)
X_test = model_norm.transform(X_test)
X_valid = model_norm.transform(X_valid)


start_time = functions.start_measures()

clf = TabNetClassifier(
    n_d=64, n_a=64, n_steps=5,
    gamma=1.5, n_independent=2, n_shared=2,
    cat_idxs=[],
    cat_dims=[],
    cat_emb_dim=1,
    lambda_sparse=1e-4, momentum=0.3, clip_value=2.,
    optimizer_fn=torch.optim.Adam,
    optimizer_params=dict(lr=2e-2),
    scheduler_params = {"gamma": 0.95, "step_size": 20},
    scheduler_fn=torch.optim.lr_scheduler.StepLR, epsilon=1e-15
)

max_epochs = 100 if not os.getenv("CI", False) else 2

clf.fit(
    X_train=X_train, y_train=y_train,
    eval_set=[(X_train, y_train), (X_valid, y_valid)],
    eval_name=['train', 'valid'],
    max_epochs=max_epochs, patience=100,
    batch_size=16384, virtual_batch_size=256
)

saved_filename = clf.save_model('modelTabNet')

predictions = clf.predict(X_test)

functions.stop_measures(start_time)

met.calculate_metrics("decision tree", y_test, predictions, average='weighted')


#Confusion Matrix 
original_labels_list = le.classes_
fig,ax = plt.subplots(figsize=(20, 20))
confusion_matrix = metrics.confusion_matrix(y_test, predictions)
cm_display = metrics.ConfusionMatrixDisplay(confusion_matrix = confusion_matrix,display_labels = original_labels_list)
cm_display.plot(ax=ax)
plt.savefig("confusion_matrix.png")
plt.show()

#importance features
def sortSecond(val):
	return val[1]

values = clf.feature_importances_
original_labels_list = le.classes_
importances = [(features[i], np.round(values[i],4)) for i in range(len(features))]
importances.sort(reverse=True, key=sortSecond)
importances


feature_names = [imp[0] for imp in importances]
importance_vals = [imp[1] for imp in importances]

# Create a horizontal bar chart
fig, ax = plt.subplots()
ax.barh(range(len(importances)), importance_vals)
ax.set_yticks(range(len(importances)))
ax.set_yticklabels(feature_names, fontsize=3) 

# Add axis labels and title
ax.set_xlabel('Importance')
ax.set_ylabel('Feature')
ax.set_title('Feature Importances')

plt.savefig('feature_importances.png', dpi=300, bbox_inches='tight')