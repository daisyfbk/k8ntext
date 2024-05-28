import json
import argparse

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('input', type=str, help='Input file')

    args = arg_parser.parse_args()

    with open(args.input, 'r') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line.startswith('#'):
            continue
        try:
            keys = set()
            data = json.loads(line)
            def get_keys(d, prefix=''):
                for k, v in d.items():
                    if isinstance(v, dict):
                        get_keys(v, f'{prefix}.{k}' if prefix else k)
                    else:
                        keys.add(f'{prefix}.{k}' if prefix else k)
            get_keys(data)
            keys = sorted(keys)

            print(f'Line {i+1} has keys: {keys}')
        except json.JSONDecodeError:
            print(f'Invalid JSON at line {i+1}: {line}')