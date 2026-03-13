from collections import Counter

def calculate_distribution(data):

    if not data:
        return {}

    counter = Counter(data)

    total = sum(counter.values())

    result = {}

    for k,v in counter.items():

        result[k] = round(v/total*100,2)

    return result