#!/bin/bash

KUBEUSER=$1
shift
KUBEGROUPS=$*

echo "Creating user $KUBEUSER with groups $KUBEGROUPS"

openssl genpkey -out ${KUBEUSER}.key -algorithm Ed25519
if [[ -z $KUBEGROUPS ]]; then
  KUBEGROUPS="external"
  openssl req -new -key ${KUBEUSER}.key -out ${KUBEUSER}.csr -subj "/CN=$KUBEUSER/O=$KUBEGROUPS"
else
  KUBEGROUPS="external $KUBEGROUPS"
  str=""
  for group in $KUBEGROUPS; do
    str="${str}/O=$group"
  done
  openssl req -new -key ${KUBEUSER}.key -out ${KUBEUSER}.csr -subj "/CN=$KUBEUSER$str"
fi

cat <<EOF | kubectl apply -f -
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: ${KUBEUSER}
spec:
  request: $(cat ${KUBEUSER}.csr | base64 | tr -d '\n')
  signerName: kubernetes.io/kube-apiserver-client
  usages:
  - client auth
EOF
kubectl certificate approve ${KUBEUSER}
kubectl get csr ${KUBEUSER} -o jsonpath='{.status.certificate}' | base64 -d > ${KUBEUSER}.crt
cp ~/.kube/config ~/${KUBEUSER}.kubeconfig
kubectl --kubeconfig ~/${KUBEUSER}.kubeconfig config set-credentials ${KUBEUSER} --client-certificate=${KUBEUSER}.crt --client-key=${KUBEUSER}.key --embed-certs=true
kubectl --kubeconfig ~/${KUBEUSER}.kubeconfig config set-context ${KUBEUSER} --cluster=kubernetes --user=${KUBEUSER}
# Set current context
kubectl --kubeconfig ~/${KUBEUSER}.kubeconfig config use-context ${KUBEUSER}
# Wipe previous contexts
kubectl --kubeconfig ~/${KUBEUSER}.kubeconfig config delete-context kubernetes-admin@kubernetes
kubectl --kubeconfig ~/${KUBEUSER}.kubeconfig config delete-user kubernetes-admin
# Add cluster-admin role
kubectl create clusterrolebinding ${KUBEUSER}-cluster-admin-binding --clusterrole=cluster-admin --user=${KUBEUSER}
