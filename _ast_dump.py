import sys, ast
from pathlib import Path

if len(sys.argv) != 2:
    print(f'Usage: python {sys.argv[0]} <script to dump>')
    sys.exit(1)

dump_script_path = Path(sys.argv[1]).resolve()

if not dump_script_path.exists():
    print(f'Error: File "{dump_script_path.name}" does not exist.')
    sys.exit(1)

script_dir = Path.cwd()

with open(dump_script_path, 'r') as file:
    source_code = file.read()
    
tree = ast.parse(source_code)

tree_dump = ast.dump(tree, indent=4)

with open(script_dir / (dump_script_path.stem + '.ast.txt'), 'w') as file:
    file.write(tree_dump)
