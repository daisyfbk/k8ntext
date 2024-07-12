import numpy as np
from sklearn.preprocessing import LabelEncoder
from label_proposer import brute_force_label_space, decode_label, encode_label


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


class AuditEncoder:
    # Takes a class, decodes it into a series of numbers, and one-hot encodes it
    def __init__(self):
        label_space = brute_force_label_space(print_result=False)

        distinct_label_ids = set()
        labels = []

        for label in label_space:
            decoded = decode_label(label)
            if 'error' in decoded:
                labels.append([0, 0, 0, 0, 0])
                continue
            decoded = decoded['raw']
            label_id = decoded['label_id']
            #label_sub_id = decoded['label_sub_id']
            #is_namespaced = decoded['is_namespaced']
            #is_single_object = decoded['is_single_object']
            #verb_id = decoded['verb_id']

            # labels.append([label_id, label_sub_id, is_namespaced, is_single_object, verb_id])
            distinct_label_ids.add(label_id)

        distinct_label_ids = sorted(list(distinct_label_ids) + [0])

        # label_id space is the biggest, so we use that to determine the size of the one-hot encoding
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(np.array(distinct_label_ids))

        self.length = len(distinct_label_ids)


    def transform(self, labels):
        ret = []
        for label in labels:
            decoded = decode_label(label)
            if 'error' in decoded:
                ret.append([0, 0, 0, 0, 0])
                continue
            decoded: dict = decoded['raw']
            label_id = decoded['label_id']
            label_sub_id = decoded['label_sub_id']
            is_namespaced = decoded['is_namespaced']
            is_single_object = decoded['is_single_object']
            verb_id = decoded['verb_id']

            tr = self.label_encoder.transform([label_id, label_sub_id, is_namespaced, is_single_object, verb_id])
            ret.append(tr)
            # tr = [
            #     self.label_encoder.transform([label_id]),
            #     self.label_encoder.transform([label_sub_id]),
            #     self.label_encoder.transform([is_namespaced]),
            #     self.label_encoder.transform([is_single_object]),
            #     self.label_encoder.transform([verb_id])
            # ]

        return np.array(ret)

    def fit(self, _):
        pass

    def fit_transform(self, labels):
        return self.transform(labels)
    
    def inverse_transform(self, one_hot_encoded_labels):
        ret = []
        for label in one_hot_encoded_labels:
            inverse_transformed = self.label_encoder.inverse_transform(label)
            label_id = inverse_transformed[0]
            label_sub_id = inverse_transformed[1]
            is_namespaced = inverse_transformed[2]
            is_single_object = inverse_transformed[3]
            verb_id = inverse_transformed[4]

            ret.append(encode_label(label_id, label_sub_id, is_namespaced, is_single_object, verb_id))
        return ret


