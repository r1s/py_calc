#!/usr/bin/env python

import ast
import itertools
import sys

is_v2 = (sys.version_info.major == 2)


class RewriteAst(ast.NodeTransformer):

    def __init__(self, *args, **kwargs):
        super(RewriteAst, self).__init__(*args, **kwargs)
        self._additional_imports = set()
    
    def find_import(self, attr):
        if attr and isinstance(attr, ast.Name) and isinstance(attr.ctx, ast.Load):
            return attr.id
        elif isinstance(attr.value, ast.Attribute) or isinstance(attr, ast.Attribute):
            v = self.find_import(attr.value)
            return '.'.join((v, attr.attr)) if v else None
        else:
            return None

    def visit_Attribute(self, attr):
        
        if attr and isinstance(attr, ast.Attribute) and isinstance(attr.ctx, ast.Load):
            import_modules_str = self.find_import(attr)
            
            if import_modules_str:
                import_module_str = import_modules_str.split('.')[0]
                try:
                    __import__(import_module_str)
                    ast_import = ast.Import(names=[ast.alias(name=import_module_str, asname=None)])
                    self._additional_imports.add(ast_import)
                except (ImportError, ) as e:
                    print(attr.value.id)
        
        return attr


def is_add_print(module_code_ast):
    childs = [child for child in ast.iter_child_nodes(module_code_ast)]

    if len(childs) > 1 or not childs:
        return False

    child = childs[0]

    if is_v2 and not isinstance(child, ast.Print):
        return True
    elif not is_v2 and not (isinstance(child, ast.Expr) and issubclass(child.value.__class__, ast.Call) and
                            child.value.func.id == 'print'):
        return True

    return False


def add_print(module_code_ast):
    print_content = module_code_ast.body[0].value
    if is_v2:
        module_code_ast.body = [ast.Print(dest=None, values=[print_content], nl=True)]
    else:
        print_name = ast.Name(id='print', ctx=ast.Load())
        print_call = ast.Call(func=print_name, args=[print_content],
                              keywords=[], starargs=None, kwargs=None)
        module_code_ast.body = [ast.Expr(value=print_call)]
    return module_code_ast
    


def code_executor(module_code):
    module_code_ast = ast.parse(module_code)
    ast_transformer = RewriteAst()

    module_code_ast = ast_transformer.visit(module_code_ast)

    child_classes = {child.__class__ for child in ast.iter_child_nodes(module_code_ast)}
    childs = [child for child in ast.iter_child_nodes(module_code_ast)]

    if is_add_print(module_code_ast):
        module_code_ast = add_print(module_code_ast)
    
    module_code_ast.body = list(itertools.chain(ast_transformer._additional_imports,
        module_code_ast.body))

    ast.fix_missing_locations(module_code_ast)
    
    exec_code = compile(module_code_ast, module_code, 'exec')

    exec(exec_code)


def test_code_executor():
    from StringIO import StringIO
    old_stdout = sys.stdout
    
    sys.stdout = StringIO()
    code_executor("2 * 2")
    assert '4' == sys.stdout.getvalue().strip()
    
    sys.stdout = StringIO()
    code_executor("math.pow(2, 3)")
    assert '8.0' == sys.stdout.getvalue().strip()

    sys.stdout = StringIO()
    code_executor("print(math.pow(2, 3))")
    assert '8.0' == sys.stdout.getvalue().strip()

    sys.stdout = StringIO()
    code_executor("datetime.datetime.now()")
    assert bool(sys.stdout.getvalue().strip()) == True

    sys.stdout = StringIO()
    code_executor("os.path.curdir")
    assert '.' == sys.stdout.getvalue().strip()
    
    sys.stdout = old_stdout


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1].strip():
        module_code = sys.argv[1].strip()
    code_executor(module_code)