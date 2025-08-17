import ast
from pathlib import Path

def stepper(file_path: Path, debug=False):
    exec_globals = {
        '__file__': str(file_path),
        '__name__': '__main__'
    }

    class ReturnValue(Exception):
        def __init__(self, value):
            self.value = value

    def located(new_node, template):
        ast.copy_location(new_node, template)
        return ast.fix_missing_locations(new_node)

    def compile_stmt(node):
        mod = ast.Module(body=[node], type_ignores=[])
        ast.fix_missing_locations(mod)
        return compile(mod, filename=str(file_path), mode='exec')

    def compile_expr(node):
        expr_mod = ast.Expression(node)
        ast.fix_missing_locations(expr_mod)
        return compile(expr_mod, filename=str(file_path), mode='eval')

    def exec_node(node, local_vars=None):
        code_obj = compile_stmt(node)
        if local_vars is None:
            exec(code_obj, exec_globals)  # use globals for both
        else:
            exec(code_obj, exec_globals, local_vars)

    def eval_ast_expr(node, local_vars=None):
        scope = exec_globals if local_vars is None else local_vars
        if isinstance(node, ast.Call):
            return eval(compile_expr(node), exec_globals, scope)
        elif isinstance(node, ast.Name):
            if local_vars is not None and node.id in local_vars:
                return local_vars[node.id]
            return exec_globals.get(node.id)
        elif isinstance(node, ast.Constant):
            return node.value
        else:
            return eval(compile_expr(node), exec_globals, scope)

    def step_through_nodes(nodes, local_vars=None):
        for node in nodes:
            if debug:
                input(f"\033[1;35m>>> \033[1;30m{ast.unparse(node)}\033[0m")
            else:
                print(f"\033[1;35m>>> \033[1;30m{ast.unparse(node)}\033[0m")

            if isinstance(node, ast.FunctionDef):
                exec_node(node, local_vars)
            elif isinstance(node, ast.ClassDef):
                exec_node(node, local_vars)
            elif isinstance(node, ast.Return):
                value = eval_ast_expr(node.value, local_vars) if node.value else None
                raise ReturnValue(value)
            elif isinstance(node, ast.Expr):
                eval_ast_expr(node.value, local_vars)
            elif isinstance(node, ast.Assign):
                value = eval_ast_expr(node.value, local_vars)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        (local_vars or exec_globals)[target.id] = value
                    else:
                        assign_node = located(
                            ast.Assign(targets=[target], value=node.value), node
                        )
                        exec_node(assign_node, local_vars)
            elif isinstance(node, ast.For):
                for item in eval_ast_expr(node.iter, local_vars):
                    if isinstance(node.target, ast.Name):
                        (local_vars or exec_globals)[node.target.id] = item
                    else:
                        assign_node = located(
                            ast.Assign(targets=[node.target], value=ast.Constant(item)),
                            node,
                        )
                        exec_node(assign_node, local_vars)
                    step_through_nodes(node.body, local_vars)
                if node.orelse:
                    step_through_nodes(node.orelse, local_vars)
            elif isinstance(node, ast.While):
                while eval_ast_expr(node.test, local_vars):
                    step_through_nodes(node.body, local_vars)
                if node.orelse:
                    step_through_nodes(node.orelse, local_vars)
            elif isinstance(node, ast.If):
                if eval_ast_expr(node.test, local_vars):
                    step_through_nodes(node.body, local_vars)
                else:
                    step_through_nodes(node.orelse, local_vars)
            elif isinstance(node, ast.With):
                managers = []
                for item in node.items:
                    context = eval_ast_expr(item.context_expr, local_vars)
                    value = context.__enter__()
                    if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                        (local_vars or exec_globals)[item.optional_vars.id] = value
                    managers.append(context.__exit__)
                try:
                    step_through_nodes(node.body, local_vars)
                finally:
                    for exit_ in reversed(managers):
                        exit_(None, None, None)
            elif isinstance(node, ast.Try):
                try:
                    step_through_nodes(node.body, local_vars)
                except Exception as e:
                    handled = False
                    for handler in node.handlers:
                        if handler.type is None or isinstance(
                            e, eval_ast_expr(handler.type, local_vars)
                        ):
                            step_through_nodes(handler.body, local_vars)
                            handled = True
                            break
                    if not handled:
                        raise
                finally:
                    step_through_nodes(node.finalbody, local_vars)
                if node.orelse:
                    step_through_nodes(node.orelse, local_vars)
            else:
                exec_node(node, local_vars)

    src = file_path.read_text(encoding="utf-8")
    parsed_ast = ast.parse(src, filename=file_path.name)
    step_through_nodes(parsed_ast.body)

if __name__ == '__main__':
    from settrace import use_dir, argv
    script_path = Path(argv[1]).resolve()
    assert script_path.name == 'test.py', 'this script is in dev!'
    with use_dir(script_path.parent):
        stepper(script_path, debug=len(argv) != 3)
