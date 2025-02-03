#!/bin/bash

curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.32/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /" | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo sed -i 's/1.31/1.32/g' /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update
sudo apt full-upgrade -y
sudo apt-mark unhold kubeadm kubelet kubectl
sudo apt-get upgrade -y kubeadm kubelet kubectl
sudo apt-mark hold kubeadm kubelet kubectl
sudo systemctl daemon-reload
sudo systemctl restart kubelet

