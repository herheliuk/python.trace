#!/usr/bin/env python3

# chatgpt.com

import ast, sys
from pathlib import Path

def parse_imports(path):
    tree = ast.parse(Path(path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names: yield (node.module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names: yield (alias.name, None)

def resolve_module(module, base_dir):
    if not module: return None
    parts = module.split(".")
    for p in [Path(base_dir, *parts).with_suffix(".py"), Path(base_dir, *parts, "__init__.py")]:
        if p.exists(): return p.resolve()
    return None

def defines_function(path, func):
    tree = ast.parse(Path(path).read_text())
    return any(isinstance(n, ast.FunctionDef) and n.name == func for n in ast.walk(tree))

def main(script):
    script_path = Path(script).resolve()
    base_dir = script_path.parent
    paths_to_trace = set()
    paths_to_trace.add(str(script_path))
    for mod, func in parse_imports(script):
        f = resolve_module(mod, base_dir)
        if f and (func is None or defines_function(f, func)):
            paths_to_trace.add(str(f))
    return paths_to_trace
    
if __name__ == "__main__":
    if len(sys.argv) < 2: print(f"Usage: python {sys.argv[0]} <script to retrive paths from>")
    else: print("\n".join(main(sys.argv[1])))
