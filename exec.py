import ast
from pathlib import Path

def stepper(file_path: Path):
    exec_globals = {'__file__': str(file_path)}

    class ReturnValue(Exception):
        def __init__(self, value):
            self.value = value

    def located(new_node, template):
        ast.copy_location(new_node, template)
        return ast.fix_missing_locations(new_node)

    def compile_node(node, mode='exec'):
        if mode == 'exec':
            mod = ast.Module(body=[node], type_ignores=[])
        else:
            mod = ast.Expression(node)
        ast.fix_missing_locations(mod)
        return compile(mod, filename=str(file_path), mode=mode)

    def exec_node(node, local_vars=None):
        exec(compile_node(node, 'exec'), exec_globals, local_vars)

    def eval_node(node, local_vars=None):
        scope = exec_globals if local_vars is None else local_vars
        if isinstance(node, ast.Name):
            if local_vars and node.id in local_vars:
                return local_vars[node.id]
            return exec_globals.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value
        return eval(compile_node(node, 'eval'), exec_globals, scope)

    def step_nodes(nodes, local_vars=None):
        for node in nodes:
            (input if len(argv) != 3 else print)(f"\033[1;31m>>> \033[33m{ast.unparse(node)}\033[1;37m")

            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                exec_node(node, local_vars)

            elif isinstance(node, ast.Return):
                value = eval_node(node.value, local_vars) if node.value else None
                raise ReturnValue(value)

            elif isinstance(node, ast.Expr):
                eval_node(node.value, local_vars)

            elif isinstance(node, ast.Assign):
                value = eval_node(node.value, local_vars)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        (local_vars or exec_globals)[target.id] = value
                    else:
                        exec_node(located(ast.Assign(targets=[target], value=node.value), node), local_vars)

            elif isinstance(node, ast.For):
                for item in eval_node(node.iter, local_vars):
                    if isinstance(node.target, ast.Name):
                        (local_vars or exec_globals)[node.target.id] = item
                    else:
                        exec_node(located(ast.Assign(targets=[node.target], value=ast.Constant(item)), node), local_vars)
                    step_nodes(node.body, local_vars)
                if node.orelse:
                    step_nodes(node.orelse, local_vars)

            elif isinstance(node, ast.While):
                while eval_node(node.test, local_vars):
                    step_nodes(node.body, local_vars)
                if node.orelse:
                    step_nodes(node.orelse, local_vars)

            elif isinstance(node, ast.If):
                branch = node.body if eval_node(node.test, local_vars) else node.orelse
                step_nodes(branch, local_vars)

            elif isinstance(node, ast.With):
                exits = []
                for item in node.items:
                    context = eval_node(item.context_expr, local_vars)
                    value = context.__enter__()
                    if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                        (local_vars or exec_globals)[item.optional_vars.id] = value
                    exits.append(context.__exit__)
                try:
                    step_nodes(node.body, local_vars)
                finally:
                    for exit_ in reversed(exits):
                        exit_(None, None, None)

            elif isinstance(node, ast.Try):
                try:
                    step_nodes(node.body, local_vars)
                except Exception as error:
                    handled = False
                    for handler in node.handlers:
                        if handler.type is None or isinstance(error, eval_node(handler.type, local_vars)):
                            step_nodes(handler.body, local_vars)
                            handled = True
                            break
                    if not handled:
                        raise
                finally:
                    step_nodes(node.finalbody, local_vars)
                if node.orelse:
                    step_nodes(node.orelse, local_vars)

            else:
                print(f"\033[1;31mUnknown node: {type(node).__name__}\033[1;37m")
                exec_node(node, local_vars)

    source = file_path.read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=file_path.name)
    step_nodes(parsed.body)

if __name__ == '__main__':
    from settrace import pretty_json, filter_scope, use_dir, argv
    script_path = Path(argv[1]).resolve()
    assert script_path.name == 'test.py', 'this script is in dev!'
    with use_dir(script_path.parent):
        stepper(script_path)
