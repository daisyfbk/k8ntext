#!/bin/bash

BASE_FOLDER=$(dirname "$0")

LOGROTATE_FILE="$BASE_FOLDER/logrotate_audit"
AUDIT_FOLDER="$BASE_FOLDER/audit-folder"
DATASET_FOLDER="$BASE_FOLDER/shared-audit-dataset"

if ! commmand -v logrotate &> /dev/null; then
    echo "logrotate could not be found, please install it."
    exit 1
fi

if [[ ! -f "$LOGROTATE_FILE" ]]; then
    echo "logrotate configuration file $LOGROTATE_FILE not found."
    exit 1
fi

if [[ ! -d "$AUDIT_FOLDER" ]]; then
    echo "Audit folder $AUDIT_FOLDER not found. Please create it and make sure audit logs are written there."
fi

if [[ ! -d "$DATASET_FOLDER" ]]; then
    echo "Dataset folder $DATASET_FOLDER not found. Please create it."
    exit 1
fi

echo "Make sure you are in the same folder as $LOGROTATE_FILE"
echo "Press any key to continue when you want to start recording..."
read -r -s
echo "Starting recording..."
sudo logrotate "$LOGROTATE_FILE"
if [[ $? -ne 0 ]]; then
    echo "Error while starting recording."
    exit 1
fi
echo "Recording started. Press any key to stop recording..."
read -r -s
echo "Stopping recording..."
sudo logrotate "$LOGROTATE_FILE"
if [[ $? -ne 0 ]]; then
    echo "Error while stopping recording."
    exit 1
fi
echo "Recording stopped."
# Find last rotated file
sudo find "$AUDIT_FOLDER"/  -type f -name "*.log.gz" -printf '%T@ %p\n' | sort -n | tail -1
echo "Is this the file you want to analyze? (y/n)"
read -r answer
if [[ "$answer" != "y" ]]; then
    echo "Please proceed manually from here."
    exit 0
fi
echo "How do you want to call the file? (omit the extension)"
read -r filename
sudo mv "$(find "$AUDIT_FOLDER"/  -type f -name "*.log.gz" -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2)" "$DATASET_FOLDER/$filename.log.gz"
cd "$DATASET_FOLDER" || exit 1
sudo gunzip "$filename.log.gz"
sudo chown "$USER" "$filename.log"
echo "File moved to $DATASET_FOLDER/$filename.log"
echo "Checking broken head: this is the first 20 characters of the file:"
echo "----------------------------------------"
head -c 20 "$filename.log"
echo "----------------------------------------"
echo "Do you want to remove the first line? (y/n)"
read -r answer
if [[ "$answer" != "n" ]]; then
	tail -n +2 "$filename.log" > "$filename.log.tmp" && mv "$filename.log.tmp" "$filename.log"
	echo "First line removed."
fi

