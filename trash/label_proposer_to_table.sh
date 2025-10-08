#!/bin/bash

[[ -z $1 ]] && echo "Usage: $0 <file_name>" && exit 1
FILE_NAME=$1

echo 'label,username,verb,resource,namespace,name,requestURI,requestReceivedTimestamp' > tmp.csv
python3 label_proposer.py -e -f $FILE_NAME | jq -rsc 'sort_by(.requestReceivedTimestamp) | .[] | [.label, .username, .verb, .resource, .namespace, .name, .requestURI, .requestReceivedTimestamp] | @csv' >> tmp.csv
pandoc tmp.csv -t org -o output.org

cat <<EOF > output2.org
#+OPTIONS: html-postamble:nil
#+OPTIONS: html-preamble:nil
EOF

cat output2.org output.org > output3.org
emacs --load ~/.emacs-export.el --batch --eval "(require 'org)" output3.org --funcall org-html-export-to-html
sed -iE 's/.*#content.*//' output.html
open output.html

rm tmp.csv output.org output2.org output3.org