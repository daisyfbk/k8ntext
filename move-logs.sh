#!/bin/bash

LOGROTATE_FILE="$HOME/logrotate_audit"
AUDIT_FOLDER="$HOME/audit-folder"
DATASET_FOLDER="$HOME/shared-audit-dataset"

echo "Make sure you are in the same folder as $LOGROTATE_FILE"
echo "Press any key to continue when you want to start recording..."
read -r -s
sudo logrotate "$LOGROTATE_FILE"
if [[ $? -ne 0 ]]; then
    echo "Error while starting recording."
    exit 1
fi
echo "Press any key to stop recording..."
read -r -s
sudo logrotate "$LOGROTATE_FILE"
if [[ $? -ne 0 ]]; then
    echo "Error while stopping recording."
    exit 1
fi
echo "Recording stopped."
# Find last rotated file
find "$AUDIT_FOLDER"/  -type f -name "*.log.gz" -printf '%T@ %p\n' | sort -n | tail -1
echo "Is this the file you want to analyze? (y/n)"
read -r -s answer
if [[ "$answer" != "n" ]]; then
    echo "Please proceed manually from here."
    exit 0
fi
echo "How do you want to call the file? (omit the extension)"
read -r filename
mv $(find "$AUDIT_FOLDER"/  -type f -name "*.log.gz" -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2) "$DATASET_FOLDER/$filename.log.gz"
cd "$DATASET_FOLDER"
gunzip "$filename.log.gz"
echo "File moved to $DATASET_FOLDER/$filename.log"
echo "Checking broken head: this is the first 20 characters of the file:"
head -c 20 "$filename.log"
echo "Do you want to remove the first line? (y/n)"
read -r -s answer
if [[ "$answer" != "n" ]]; then
	tail -n +2 "$filename.log" > "$filename.log.tmp" && mv "$filename.log.tmp" "$filename.log"
	echo "First line removed."
fi

