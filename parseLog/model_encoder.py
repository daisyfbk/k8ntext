import numpy as np

class RisingEncoder:
    def __init__(self):
        self.mapping = {}
        self.reverse_mapping = {}
        self.next_id = 0  # Track the next available ID

    def fit(self, strings):
        for idx, s in enumerate(strings):
            if s not in self.mapping:
                self.mapping[s] = self.next_id
                self.reverse_mapping[self.next_id] = s
                self.next_id += 1

    def transform(self, strings):
        transformed_strings = []
        for s in strings:
            if s in self.mapping:
                transformed_strings.append(self.mapping[s])
            else:
                # Dynamically assign a new ID for unseen strings
                self.mapping[s] = self.next_id
                self.reverse_mapping[self.next_id] = s
                transformed_strings.append(self.next_id)
                self.next_id += 1  # Update the next available ID
        return np.array(transformed_strings)
    
    def fit_transform(self, strings):
        self.fit(strings)
        return self.transform(strings)

    def inverse_transform(self, ids):
        return [self.reverse_mapping.get(i, "UNKNOWN") for i in ids]