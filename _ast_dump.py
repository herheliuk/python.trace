#!/usr/bin/env python3

import sys, ast
from pathlib import Path

if __name__ == '__main__':
    assert len(sys.argv) == 2, f'Usage: python {sys.argv[0]} <script to dump>'

    script_path = Path(sys.argv[1]).resolve()

    assert script_path.exists(), f'File "{script_path.name}" does not exist.'

    source_code = script_path.read_text()
    
    ast_tree = ast.parse(source_code, filename=script_path.name)
    
    tree_dump = ast.dump(ast_tree, indent=4)

    output_file = Path.cwd() / (script_path.stem + '.ast.txt')

    output_file.write_text(tree_dump)
