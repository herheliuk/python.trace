from pathlib import Path
import ast

def find_used_python_scripts(script_path: Path) -> list[Path]:
    script_dir = script_path.parent
    content = script_path.read_text()
    tree = ast.parse(content)
    scripts = {script_path}

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = node.names if hasattr(node, 'names') else []
            for alias in names:
                # For ast.Import, alias.name is the module name
                # For ast.ImportFrom, node.module is the module name
                name = alias.name if module is None else module
                parts = name.split('.')
                candidate = script_dir.joinpath(*parts).with_suffix('.py')
                if candidate.exists():
                    scripts.add(candidate)

    return scripts
