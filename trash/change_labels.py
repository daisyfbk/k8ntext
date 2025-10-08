import json

mappings = [
(3281040, 3276944, [
"b675a6cd-f574-43c3-9278-98ba250d88b4",
"55f73648-ad44-43cc-bcdf-f4e4f9dddfcf",
"86791602-f020-4370-8455-f3939e8e91d6",
"a8db3567-6717-45e0-a76f-74c51d6b3dd7",
"93a0c2c0-4e70-4371-a822-05a4745d41d6",
"dba93c17-2a62-45d9-89c7-abc56c819ae8",
"955287ab-17cb-4858-ba98-02e56320be15",
"1890a5f5-ede3-4ea7-ba3d-ecc8b9a88e03",
"439bacd2-f5d9-4404-a5a7-7f68971150e2",
"849c710c-5092-4d57-9d84-b59aa8db43b2",
"ec654784-1d62-468a-8170-f92237cffea6",
"282ab0a2-b40a-4766-aafa-0179e71e3227",
"f4ea911b-9bb0-4ab3-8d6d-a377fc72bd73",
]),
(3281056, 3276960, [
"00e0e575-cd36-4615-8b7f-110d0b02937f",
"bf8619c6-b128-4f62-9367-06d9fde1aa67",
"63241329-6cfb-49a1-935c-816f20703623",
"dd915515-056d-46be-9f9e-553b2b8b2651",
"d449a9e9-f331-4f48-a796-56635b9acf65",
"0a47eed1-30a9-4ea8-88e5-db4146eecbb6",
"fa21a0d3-866b-43e8-996f-c3fa0f203be2",
"0ffce7df-0155-4113-ba74-656362d154b3",
"ded472d5-2ff0-40cc-929e-e37f73944576",
"1acaf6c8-2c60-4f82-a716-57b250944301",
"76531fc2-b7b9-458c-b1cb-87fd752b30f0",
"b07bdf2d-f8cd-4e12-8725-c9d356d71ec6",
"e522e53f-4941-45fe-b766-34ddeeeb0677",
])]

lines = []
with open('0-stitched-category-4n.json_apionly') as f:
    for line in f:
        lines.append(json.loads(line))

for label, new_label, ids in mappings:
    for line in lines:
        if line['auditID'] in ids and line['label'] == label:
            print('Changing label from', label, 'to', new_label)
            line['label'] = new_label
            ids.remove(line['auditID'])

    print("Leftover IDs:", ids)
            
with open('0-stitched-category-4n.json_apionly2', 'w') as f:
    for line in lines:
        f.write(json.dumps(line, separators=(',', ':')) + "\n")