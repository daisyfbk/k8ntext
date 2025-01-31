#!/bin/bash

curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.32/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
sudo sed -i 's/1.28/1.29/g' /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update
sudo apt full-upgrade -y
sudo apt-mark unhold kubeadm kubelet kubectl
sudo apt-get upgrade kubeadm kubelet kubectl
sudo apt-mark hold kubeadm kubelet kubectl
sudo systemctl daemon-reload
sudo systemctl restart kubelet

