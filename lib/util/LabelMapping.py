import csv
import numpy as np

class LabelMapping:
    def __init__(self, filename, keyField, default_index):
        self.mapping = LabelMapping.load_csv(filename, keyField)
        self.indices = list(set([m['index'] for k,m in self.mapping.items()]))
        self.max_index = max(self.indices)
        self.default_index = default_index

    def get_index(self, label):
        if label in self.mapping:
            return self.mapping[label]['index']
        else:
            return self.default_index

    def get_index_one_hot(self, label):
        index = self.get_index(label)
        return LabelMapping.encode_one_hot(index, self.max_index + 1)

    def to_dict(self):
        return { 'mapping': self.mapping, 'max_index': self.max_index, 'default_index': self.default_index }

    @staticmethod
    def load_csv(filename, keyField):
        with open(filename) as csvfile:
            reader = csv.DictReader(csvfile)
            rows = {}
            for row in reader:
                row['index'] = int(row['index'])
                rows[row[keyField]] = row
            return rows

    @staticmethod
    def encode_one_hot(i, n):
        # Encode a number
        v = np.zeros(n)
        v[i] = 1
        return v


