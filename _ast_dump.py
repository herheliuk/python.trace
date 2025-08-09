#!/usr/bin/env python3

import sys, ast
from pathlib import Path

assert len(sys.argv) == 2
dump_script_path = Path(sys.argv[1]).resolve()
assert dump_script_path.exists()

script_dir = Path.cwd()

source_code = dump_script_path.read_text()
    
tree = ast.parse(source_code)

tree_dump = ast.dump(tree, indent=4)

output_file = script_dir / (dump_script_path.stem + '.ast.txt')

output_file.write_text(tree_dump)
