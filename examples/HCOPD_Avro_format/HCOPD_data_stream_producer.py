

import os
import sys
sys.path.append(sys.path[0] + "/../..")

from kafkaml_datasources import AvroSink

import pandas as pd

from sklearn import preprocessing

import logging

logging.basicConfig(level=logging.INFO)

# Defaults to 1 (the deployment id every doc/tutorial example assumes) -
# override with KAFKAML_DEPLOYMENT_ID so this script can be re-run
# against a freshly created deployment without editing the file, e.g.
# from the real-execution CI job in .github/workflows/examples.yml.
deployment_id = int(os.environ.get("KAFKAML_DEPLOYMENT_ID", "1"))

copd_data = pd.read_csv('HCOPD_Dataset.csv')
"""Reads the HCOPD dataset"""

copd_data_columns = copd_data.columns

features = pd.DataFrame(preprocessing.scale(copd_data[copd_data_columns[copd_data_columns != 'Diagnosis']]))
"""All columns except Diagnosis"""

diagnosis = copd_data['Diagnosis']
"""Diagnosis column"""

hcopd = AvroSink(boostrap_servers='127.0.0.1:9094', topic='hcopd', deployment_id=deployment_id,
        data_scheme_filename='data_scheme.avsc', label_scheme_filename='label_scheme.avsc',
        description='COPD dataset', validation_rate=0.1, test_rate=0.1)

for i in range (0, copd_data.shape[0]):
    data  = {"gender": features[0][i], "age": features[1][i], "smoking": features[2][i]}
    label = {"diagnosis": bool(diagnosis[i])}
    hcopd.send_avro(data, label)

hcopd.close()