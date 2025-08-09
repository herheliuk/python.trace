from pathlib import Path
import ast

def find_python_imports(script_path: Path, should_exist: bool = True) -> set[Path]:
    script_dir = script_path.parent
    content = script_path.read_text()
    tree = ast.parse(content)
    scripts = {script_path}

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            base_name = node.module if isinstance(node, ast.ImportFrom) else None
            for alias in node.names:
                name = base_name or alias.name
                candidate = script_dir.joinpath(*name.split('.')).with_suffix('.py')
                if not should_exist or candidate.exists():
                    scripts.add(candidate)

    return scripts
