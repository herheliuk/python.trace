#!/usr/bin/env python3

import sys, ast
from pathlib import Path

if __name__ == '__main__':
    assert len(sys.argv) == 2, f'Usage: python {sys.argv[0]} <script to dump>'

    dump_script_path = Path(sys.argv[1]).resolve()

    assert dump_script_path.exists(), f'File "{dump_script_path.name}" does not exist.'

    source_code = dump_script_path.read_text()
    
    ast_tree = ast.parse(source_code)
    
    tree_dump = ast.dump(ast_tree, indent=4)

    output_file = Path.cwd() / (dump_script_path.stem + '.ast.txt')

    output_file.write_text(tree_dump)
