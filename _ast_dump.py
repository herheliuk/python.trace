import sys, ast
from pathlib import Path

if len(sys.argv) != 2:
    print(f'Usage: python {sys.argv[0]} <script to dump>')
    sys.exit(1)

script_path = Path(sys.argv[1]).resolve()

this_script_dir = Path.cwd()

with open(script_path, 'r') as file:
    source_code = file.read()
    
tree = ast.parse(source_code)

tree_dump = ast.dump(tree, indent=4)

with open(this_script_dir / (script_path.stem + '.ast.txt'), 'w') as file:
    file.write(tree_dump)
