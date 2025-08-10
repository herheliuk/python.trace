from pathlib import Path
import ast

def find_python_imports(script_path: Path) -> set[Path]:
    script_dir = script_path.parent
    content = script_path.read_text()
    tree = ast.parse(content)
    script_paths = {script_path}

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            base_name = node.module if isinstance(node, ast.ImportFrom) else None
            for alias in node.names:
                name = base_name or alias.name
                candidate = script_dir.joinpath(*name.split('.')).with_suffix('.py')
                if candidate.exists():
                    script_paths.add(candidate)

    return script_paths
