#!/usr/bin/env python3

from utils.context_managers import apply_dir

from ast import parse, unparse, Module
from sys import argv, exit
from pathlib import Path

def exec_ast_segments(file_path: Path):
    source = file_path.read_text(encoding='utf-8')
    
    parsed_ast = parse(source, filename=file_path.name)

    exec_globals = {}
    
    for node in parsed_ast.body:
        code_str = unparse(node)
        
        input(f">>> {code_str}")
        
        single_node_ast = Module(body=[node], type_ignores=[])
        
        code_obj = compile(
            single_node_ast,
            filename=file_path,
            mode='exec',
            dont_inherit=True
        )
        
        exec(code_obj, exec_globals)

if __name__ == "__main__":
    script = Path(argv[1]).resolve()
    with apply_dir(script.parent):
        try:
            exec_ast_segments(script)
        except KeyboardInterrupt:
            exit(1)
