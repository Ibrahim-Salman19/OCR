import ast
import os


def find_bare_excepts(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ExceptHandler):
                            if node.type is None:
                                print(f"BARE EXCEPT: {path} at line {node.lineno}")
                except Exception as e:
                    print(f"Error parsing {path}: {e}")


if __name__ == "__main__":
    find_bare_excepts("blast_ocr")
