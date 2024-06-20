# {"kind":"Event","apiVersion":"audit.k8s.io/v1","level":"RequestResponse","auditID":"a8b8b8ec-5c27-4643-8484-44ae14481bd1","stage":"ResponseComplete","requestURI":"/api/v1/namespaces?fieldManager=kubectl-create&fieldValidation=Strict","verb":"create","user":{"username":"mfranzil","groups":["system:authenticated"]},"sourceIPs":["192.168.42.228"],"userAgent":"kubectl/v1.30.1 (darwin/arm64) kubernetes/6911225","objectRef":{"resource":"namespaces","name":"rising","apiVersion":"v1"},"responseStatus":{"metadata":{},"code":201},"requestObject":{"kind":"Namespace","apiVersion":"v1","metadata":{"name":"rising","creationTimestamp":null,"labels":{"kubernetes.io/metadata.name":"rising"}},"spec":{},"status":{"phase":"Active"}},"responseObject":{"kind":"Namespace","apiVersion":"v1","metadata":{"name":"rising","uid":"b9b6b929-ccaf-4519-8e1d-1f48baf724c4","resourceVersion":"2212024","creationTimestamp":"2024-05-28T07:48:35Z","labels":{"kubernetes.io/metadata.name":"rising"},"managedFields":[{"manager":"kubectl-create","operation":"Update","apiVersion":"v1","time":"2024-05-28T07:48:35Z","fieldsType":"FieldsV1","fieldsV1":{"f:metadata":{"f:labels":{".":{},"f:kubernetes.io/metadata.name":{}}}}}]},"spec":{"finalizers":["kubernetes"]},"status":{"phase":"Active"}},"requestReceivedTimestamp":"2024-05-28T07:48:35.015449Z","stageTimestamp":"2024-05-28T07:48:35.025311Z","annotations":{"authorization.k8s.io/decision":"allow","authorization.k8s.io/reason":"RBAC: allowed by ClusterRoleBinding \"mfranzil-cluster-admin-binding\" of ClusterRole \"cluster-admin\" to User \"mfranzil\""}}
# {"kind":"Event","apiVersion":"audit.k8s.io/v1","level":"RequestResponse","auditID":"e9167b5a-27c6-4871-a03f-095cf14a8be1","stage":"ResponseComplete","requestURI":"/api/v1/namespaces/rising/resourcequotas","verb":"list","user":{"username":"system:apiserver","uid":"48121d14-4094-4477-a7e7-a3f666cfd4ac","groups":["system:masters"]},"sourceIPs":["::1"],"userAgent":"kube-apiserver/v1.28.7 (linux/amd64) kubernetes/c8dcb00","objectRef":{"resource":"resourcequotas","namespace":"rising","apiVersion":"v1"},"responseStatus":{"metadata":{},"code":200},"responseObject":{"kind":"ResourceQuotaList","apiVersion":"v1","metadata":{"resourceVersion":"2212023"},"items":[]},"requestReceivedTimestamp":"2024-05-28T07:48:35.018446Z","stageTimestamp":"2024-05-28T07:48:35.020676Z","annotations":{"authorization.k8s.io/decision":"allow","authorization.k8s.io/reason":""}}
# {"kind":"Event","apiVersion":"audit.k8s.io/v1","level":"RequestResponse","auditID":"a1a35ad1-a8be-44d2-8a85-11fb65f5d9d2","stage":"ResponseComplete","requestURI":"/api/v1/namespaces/rising/serviceaccounts","verb":"create","user":{"username":"system:serviceaccount:kube-system:service-account-controller","uid":"7a0663b3-19cc-4167-acbb-8c5cd008b9f3","groups":["system:serviceaccounts","system:serviceaccounts:kube-system","system:authenticated"]},"sourceIPs":["192.168.38.9"],"userAgent":"kube-controller-manager/v1.28.7 (linux/amd64) kubernetes/c8dcb00/system:serviceaccount:kube-system:service-account-controller","objectRef":{"resource":"serviceaccounts","namespace":"rising","name":"default","apiVersion":"v1"},"responseStatus":{"metadata":{},"code":201},"requestObject":{"kind":"ServiceAccount","apiVersion":"v1","metadata":{"name":"default","namespace":"rising","creationTimestamp":null}},"responseObject":{"kind":"ServiceAccount","apiVersion":"v1","metadata":{"name":"default","namespace":"rising","uid":"06f4b0ff-0ee4-47cf-be66-3a473236be6b","resourceVersion":"2212025","creationTimestamp":"2024-05-28T07:48:35Z"}},"requestReceivedTimestamp":"2024-05-28T07:48:35.026235Z","stageTimestamp":"2024-05-28T07:48:35.032918Z","annotations":{"authorization.k8s.io/decision":"allow","authorization.k8s.io/reason":"RBAC: allowed by ClusterRoleBinding \"system:controller:service-account-controller\" of ClusterRole \"system:controller:service-account-controller\" to ServiceAccount \"service-account-controller/kube-system\""}}
# {"kind":"Event","apiVersion":"audit.k8s.io/v1","level":"RequestResponse","auditID":"40b01e16-9be9-4b69-920f-054baa07b199","stage":"ResponseComplete","requestURI":"/api/v1/namespaces/rising/configmaps","verb":"create","user":{"username":"system:serviceaccount:kube-system:root-ca-cert-publisher","uid":"ec40ee1f-796c-45ca-b67f-e9b6352948ec","groups":["system:serviceaccounts","system:serviceaccounts:kube-system","system:authenticated"]},"sourceIPs":["192.168.38.9"],"userAgent":"kube-controller-manager/v1.28.7 (linux/amd64) kubernetes/c8dcb00/system:serviceaccount:kube-system:root-ca-cert-publisher","objectRef":{"resource":"configmaps","namespace":"rising","name":"kube-root-ca.crt","apiVersion":"v1"},"responseStatus":{"metadata":{},"code":201},"requestObject":{"kind":"ConfigMap","apiVersion":"v1","metadata":{"name":"kube-root-ca.crt","creationTimestamp":null,"annotations":{"kubernetes.io/description":"Contains a CA bundle that can be used to verify the kube-apiserver when using internal endpoints such as the internal service IP or kubernetes.default.svc. No other usage is guaranteed across distributions of Kubernetes clusters."}},"data":{"ca.crt":"-----BEGIN CERTIFICATE-----\nMIIDBTCCAe2gAwIBAgIIYJVUD7dVUq8wDQYJKoZIhvcNAQELBQAwFTETMBEGA1UE\nAxMKa3ViZXJuZXRlczAeFw0yNDAyMTkwODQ1MzFaFw0zNDAyMTYwODUwMzFaMBUx\nEzARBgNVBAMTCmt1YmVybmV0ZXMwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK\nAoIBAQCvH4LWiy1kY1jpgWAdbG9Fjn6hOhhZCJIDsY8frlQslUUsJshV1w9vfJIv\nqss3NbbTTDPEPF0SHzb/yywPB9YNDZY5P8h1G77TYOJAT8DeP6FMqYzGf9HwX7aq\nqjdkvLGvHa2oU2MORkvVV+0EWRbawhmUJ5lk546UaBZ+ikec7ISYK4n/0eEYBWKi\n3JGZJpyPzBTYooeMtHHB+Y/j+X8tjhms1inIkJIgkHKSdxR2t6K0A5aFsAwZBnw5\nL1vpy32w1THRLLEjITY3rdZp3UFLuWiQw8bdKn/7L9Ax9BzIvzBamr7lo/I6gB4v\nHJ4f9PBdTt99FpELu4iBJtgNk5KbAgMBAAGjWTBXMA4GA1UdDwEB/wQEAwICpDAP\nBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBRuEYWRlleeOHo9DfKmDACbiuRJXjAV\nBgNVHREEDjAMggprdWJlcm5ldGVzMA0GCSqGSIb3DQEBCwUAA4IBAQBY/n1cp870\nYzwVGXfIrI1T035+EGxMVkryqACFUySlgMOVdjuGIaBboe4y9LpZjzREhwodHb02\n+nsJn/lhcCuMpm8p8c6dtloW2MbusF3/iddONip8CEWLqZAOmp55HOuCNetTUGP3\nicftoADba7Fo5WgYJS1TIKCgrv8U7jlGAAHV6kFjazSyUIl1G4NBqqrAu+BZ1in6\nTUFUJB70TxYk2ic25RGDepvAGCzqajkQ8rNbCp5Wxo3BWTSLvWuJa2RP/W8dkaGw\nkatynrqIS3YwMf2t2xMfgVg0VN79uhuJ5loedY+pnbLRAAUupkkAGj5o543lLav/\noyXly0tAzhQq\n-----END CERTIFICATE-----\n"}},"responseObject":{"kind":"ConfigMap","apiVersion":"v1","metadata":{"name":"kube-root-ca.crt","namespace":"rising","uid":"7b664337-bc28-4633-bc59-091eec145c71","resourceVersion":"2212026","creationTimestamp":"2024-05-28T07:48:35Z","annotations":{"kubernetes.io/description":"Contains a CA bundle that can be used to verify the kube-apiserver when using internal endpoints such as the internal service IP or kubernetes.default.svc. No other usage is guaranteed across distributions of Kubernetes clusters."},"managedFields":[{"manager":"kube-controller-manager","operation":"Update","apiVersion":"v1","time":"2024-05-28T07:48:35Z","fieldsType":"FieldsV1","fieldsV1":{"f:data":{".":{},"f:ca.crt":{}},"f:metadata":{"f:annotations":{".":{},"f:kubernetes.io/description":{}}}}}]},"data":{"ca.crt":"-----BEGIN CERTIFICATE-----\nMIIDBTCCAe2gAwIBAgIIYJVUD7dVUq8wDQYJKoZIhvcNAQELBQAwFTETMBEGA1UE\nAxMKa3ViZXJuZXRlczAeFw0yNDAyMTkwODQ1MzFaFw0zNDAyMTYwODUwMzFaMBUx\nEzARBgNVBAMTCmt1YmVybmV0ZXMwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK\nAoIBAQCvH4LWiy1kY1jpgWAdbG9Fjn6hOhhZCJIDsY8frlQslUUsJshV1w9vfJIv\nqss3NbbTTDPEPF0SHzb/yywPB9YNDZY5P8h1G77TYOJAT8DeP6FMqYzGf9HwX7aq\nqjdkvLGvHa2oU2MORkvVV+0EWRbawhmUJ5lk546UaBZ+ikec7ISYK4n/0eEYBWKi\n3JGZJpyPzBTYooeMtHHB+Y/j+X8tjhms1inIkJIgkHKSdxR2t6K0A5aFsAwZBnw5\nL1vpy32w1THRLLEjITY3rdZp3UFLuWiQw8bdKn/7L9Ax9BzIvzBamr7lo/I6gB4v\nHJ4f9PBdTt99FpELu4iBJtgNk5KbAgMBAAGjWTBXMA4GA1UdDwEB/wQEAwICpDAP\nBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBRuEYWRlleeOHo9DfKmDACbiuRJXjAV\nBgNVHREEDjAMggprdWJlcm5ldGVzMA0GCSqGSIb3DQEBCwUAA4IBAQBY/n1cp870\nYzwVGXfIrI1T035+EGxMVkryqACFUySlgMOVdjuGIaBboe4y9LpZjzREhwodHb02\n+nsJn/lhcCuMpm8p8c6dtloW2MbusF3/iddONip8CEWLqZAOmp55HOuCNetTUGP3\nicftoADba7Fo5WgYJS1TIKCgrv8U7jlGAAHV6kFjazSyUIl1G4NBqqrAu+BZ1in6\nTUFUJB70TxYk2ic25RGDepvAGCzqajkQ8rNbCp5Wxo3BWTSLvWuJa2RP/W8dkaGw\nkatynrqIS3YwMf2t2xMfgVg0VN79uhuJ5loedY+pnbLRAAUupkkAGj5o543lLav/\noyXly0tAzhQq\n-----END CERTIFICATE-----\n"}},"requestReceivedTimestamp":"2024-05-28T07:48:35.027411Z","stageTimestamp":"2024-05-28T07:48:35.038367Z","annotations":{"authorization.k8s.io/decision":"allow","authorization.k8s.io/reason":"RBAC: allowed by ClusterRoleBinding \"system:controller:root-ca-cert-publisher\" of ClusterRole \"system:controller:root-ca-cert-publisher\" to ServiceAccount \"root-ca-cert-publisher/kube-system\""}

# k-means clustering for analyzing the logs

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Load the data
data = pd.read_json('~/Downloads/namespace-N1.log', lines=True)

# Keep only the relevant columns
columns = [
    "requestURI",
    "verb",
    "user",
]

data = data[columns]

for column in columns:
    # truncate requestURI to the ?
    if column == "requestURI":
        data[column] = data[column].apply(lambda x: x.split("?")[0])
    elif column == "user":
        data[column] = data[column].apply(lambda x: x['username'])
    else:
        data[column] = data[column].astype(str)

print(data.head())

# Encode categorical columns
data_encoded = pd.get_dummies(data, columns=columns)

# Standardize the data
scaler = StandardScaler()
np_scaled = scaler.fit_transform(data_encoded)

# apply k-means clustering
kmeans = KMeans(n_clusters=10)
kmeans.fit(np_scaled)

# Add the cluster labels to the original data
data['cluster'] = kmeans.predict(np_scaled)

# Sort the data by cluster
data = data.sort_values('cluster')

# Plot URI and user by cluster
from matplotlib import pyplot as plt

plt.figure(figsize=(20, 10))

# write x ticks vertically
plt.xticks(rotation=90)
# shrink y-axis to fit the text labels
plt.subplots_adjust(left=0.4, right=0.9, top=0.9, bottom=0.6)
# order y-axis alphabetically
data = data.sort_values('user')

for cluster in data['cluster'].unique():
    plt.scatter(data[data['cluster'] == cluster]['requestURI'], data[data['cluster'] == cluster]['user'], label='cluster ' + str(cluster))


plt.legend()

plt.show()
