import sys, ast

with open(sys.argv[1], 'r') as file:
    source_code = file.read()
    
tree = ast.parse(source_code)

tree_dump = ast.dump(tree, indent=4)

with open(f'{sys.argv[1].rpartition('.')[0]}.txt', 'w') as file:
    file.write(tree_dump)
    
print(tree_dump)
