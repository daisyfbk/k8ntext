import argparse
import re

class QuerySyntaxError(Exception):
    pass


allowed_keys = [
    'username',
    'verb',
    'resource',
    'subresource',
    'namespace',
    'name',
    'requestTime',
    'completionTime'
]

remap_keys = {
    'requestTime': 'requestReceivedTimestamp',
    'completionTime': 'stageTimestamp',
}

def evaluate_query(query):
    # Try evaluating the query to see if it is valid.
    filtered_keys = [key for key in allowed_keys]
    filtered_keys = [remap_keys.get(key, key) for key in filtered_keys]
    obj = {k: "a" for k in filtered_keys}
    
    try:
        eval(query)
    except SyntaxError as e:
        raise QuerySyntaxError(f"The query language is not valid: {e}")
    except TypeError as e:
        raise QuerySyntaxError(f"All keys must be strings.")
    except KeyError as e:
        raise QuerySyntaxError(f"Key '{e}' is not allowed.")
    except Exception as e:
        raise QuerySyntaxError(f"Invalid query: {e}")

def convert_query(query):
    # .key == regex(".*franzil") -> re.match(".*franzil", .key)
    query = re.sub(r'\.(\w+) ?== ?regex\("(.+)"\)', r"re.match('\2', .\1)", query)

    # Reject all regex queries that do not use the equal operator, so >, <, >=, <=, !=.
    if re.search(r'\.(\w+) ?[><!=]= ?regex\("(.+)"\)', query):
        raise QuerySyntaxError("Regex queries must use the equal operator.")

    # exists(.namespace) -> 'namespace' in obj and .namespace is not None
    query = re.sub(r'exists\(\.(\w+)\)', r"('\1' in obj and obj['\1'] is not None)", query)
    print(query)

    # Replace all items of the type of .key with obj['key']
    # Also filter the keys.
    keys = re.findall(r' \.(\w+)', query)
    for key in keys:
        if key not in allowed_keys:
            raise QuerySyntaxError(f"Key '{key}' is not allowed.")
        if key in remap_keys:
            query = re.sub(rf'\.{key}', f"obj.get('{remap_keys[key]}', None)", query)
        else:
            query = re.sub(rf'\.{key}', f"obj.get('{key}', None)", query)

    evaluate_query(query)
    
    return query

def main():
    parser = argparse.ArgumentParser(description='Convert custom query syntax to Python boolean expression.')
    parser.add_argument('query', type=str, help='The query string to convert. MUST be enclosed in single quotes. Double quotes can be used within the query string.')
    args = parser.parse_args()

    query = args.query
    try:
        python_query = convert_query(query)
    except QuerySyntaxError as e:
        print(f"Query conversion failed: {e}")
        return
    
    print(f"Converted Python boolean filter: {python_query}")

if __name__ == "__main__":
    main()