import pandas as pd
import json
import numpy as np

def serialize_nested(obj):
    """Recursively serializes nested structures."""
    if isinstance(obj, dict):
        return json.dumps(obj)
    elif isinstance(obj, list):
        return json.dumps(obj)
    else:
        return str(obj)

# Step 1: Read the JSONLines file
input_file = 'role-R3.log_edited'
with open(input_file) as f:
    lines = f.read().splitlines()

# Step 2: Load JSON objects into a DataFrame
df_inter = pd.DataFrame(lines)
df_inter.columns = ['json_element']

# Step 3: Normalize the JSON data
df_final = pd.json_normalize(df_inter['json_element'].apply(json.loads))

#df_final = df_final[df_final['requestURI'] == '/apis/certificates.k8s.io/v1/certificatesigningrequests/rising-user']

#df_final = df_final.iloc[2:4]

# Display the final DataFrame
for column in df_final.columns.to_list():
    try:
        serialized_values = df_final[column].apply(serialize_nested).tolist()
        if len(set(serialized_values)) == 1:
            #print(f"{column}: {serialized_values}")
            continue
        
    except Exception as e:
        print(f"Error processing column '{column}': {e}")


    print(f"{column}: {df_final[column].tolist()}")