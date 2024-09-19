import os 
import json

files = []
for root, children, f in (fragments := os.walk('/home/rising/shared-audit-dataset/fragments')):
    files.extend([os.path.join(root, file) for file in f])
files = [file for file in files if file.endswith('_labelled')]

for file in files:
    out = []
    with open(file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            o = json.loads(line)
            for wrong_label in [41376]:
                if wrong_label == o['label']:
                    print(file)
    #         out.append(json.dumps(o, separators=(',', ':')))
    # with open(file + "2", 'w') as f:
    #     for line in out:
    #         f.write(line + '\n')

