import ast
from pathlib import Path

def stepper(file_path: Path, debug=False):
    exec_globals = {'__file__': str(file_path)}
    exec_locals = {}

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
        exec(code_obj, exec_globals, local_vars or exec_locals)

    def eval_ast_expr(node, local_vars):
        if isinstance(node, ast.Call):
            return eval(compile_expr(node), exec_globals, local_vars)
        elif isinstance(node, ast.Name):
            return local_vars.get(node.id, exec_globals.get(node.id))
        elif isinstance(node, ast.Constant):
            return node.value
        else:
            return eval(compile_expr(node), exec_globals, local_vars)

    def step_through_nodes(nodes, local_vars=None):
        local_vars = local_vars or exec_locals
        for node in nodes:
            if debug:
                input(f">>> {ast.unparse(node)}")
            else:
                print(f">>> {ast.unparse(node)}")
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
                        local_vars[target.id] = value
                    else:
                        assign_node = located(ast.Assign(targets=[target], value=node.value), node)
                        exec_node(assign_node, local_vars)
            elif isinstance(node, ast.For):
                for item in eval_ast_expr(node.iter, local_vars):
                    if isinstance(node.target, ast.Name):
                        local_vars[node.target.id] = item
                    else:
                        assign_node = located(ast.Assign(targets=[node.target], value=ast.Constant(item)), node)
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
                        local_vars[item.optional_vars.id] = value
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
                        if handler.type is None or isinstance(e, eval_ast_expr(handler.type, local_vars)):
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
    step_through_nodes(parsed_ast.body, exec_locals)
    return exec_globals, exec_locals

if __name__ == '__main__':
    from settrace import pretty_json, filter_scope, use_dir, argv
    script_path = Path(argv[1]).resolve()
    with use_dir(script_path.parent):
        exec_globals, exec_locals = stepper(script_path, debug=len(argv) != 3)
    print(pretty_json(filter_scope({**exec_globals, **exec_locals})))
