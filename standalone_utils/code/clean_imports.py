# standalone_utils/code/clean_imports.py
#
# Purpose: Parses Python files via AST to hoist, deduplicate, and aggressively 
# filter out unused import statements from the global and local scopes.

import ast
from pathlib import Path

def find_project_root(current_path: Path) -> Path:
    for parent in current_path.resolve().parents:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists() or (parent / "requirements.txt").exists():
            return parent
    return current_path.resolve().parent

def should_skip(path: Path) -> bool:
    # Explicitly ignore virtual environments, cache, utility modules, and hidden IDE directories
    ignored_patterns = {
        ".venv", "venv", "env", "site-packages", ".git", 
        ".pytest_cache", "__pycache__", ".egg-info", "build", "dist",
        "standalone_utils"
    }
    return any(part.startswith('.') or part in ignored_patterns for part in path.parts)

def analyze_usages_and_imports(tree: ast.AST):
    """Walks the AST to find all defined imports and all code-wide identifier usages."""
    imported_names = []  # List of tuples: (node, exact_alias_or_name, reconstructed_import_string)
    used_identifiers = set()

    for node in ast.walk(tree):
        # 1. Capture plain imports: import os, import math as m
        if isinstance(node, ast.Import):
            for alias in node.names:
                name_to_check = alias.asname if alias.asname else alias.name
                # Submodules (e.g. 'os.path') need to be checked by the root module name ('os')
                root_name = name_to_check.split('.')[0]
                single_import_node = ast.Import(names=[alias])
                imported_names.append((node, root_name, ast.unparse(single_import_node)))

        # 2. Capture from-imports: from datetime import datetime as dt
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == '*':
                    # If star import is used, we preserve the statement safely
                    imported_names.append((node, '*', ast.unparse(node)))
                    continue
                name_to_check = alias.asname if alias.asname else alias.name
                single_import_node = ast.ImportFrom(module=node.module, names=[alias], level=node.level)
                imported_names.append((node, name_to_check, ast.unparse(single_import_node)))

        # 3. Capture all variables, function calls, and decorators used in code
        elif isinstance(node, ast.Name):
            if not isinstance(node.ctx, ast.Store):  # Exclude target assignment names themselves
                used_identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Capture cases like 'sys.argv' where 'sys' is the base identifier
            curr_node = node
            while isinstance(curr_node, ast.Attribute):
                curr_node = curr_node.value
            if isinstance(curr_node, ast.Name):
                used_identifiers.add(curr_node.id)

    return imported_names, used_identifiers

def clean_file_imports(file_path: Path, root_path: Path):
    relative_path = file_path.relative_to(root_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        if not source.strip():
            return

        tree = ast.parse(source)
        lines = source.splitlines()
        
        imported_names, used_identifiers = analyze_usages_and_imports(tree)

        if not imported_names:
            return

        # Track which lines belonged to old imports to clear them out safely
        lines_to_remove = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for line_num in range(node.lineno, node.end_lineno + 1):
                    lines_to_remove.add(line_num - 1)

        # Reconstruct only the unique AND used imports
        unique_imports = {}
        for node, name, import_str in imported_names:
            # Keep if it's a wildcard import OR if the imported name is actively referenced in the AST
            if name == '*' or name in used_identifiers:
                unique_imports[import_str] = None

        # Clean old import lines from the source text block
        cleaned_source_lines = [
            line for idx, line in enumerate(lines) if idx not in lines_to_remove
        ]
        remaining_code = "\n".join(cleaned_source_lines).lstrip()

        # Preserve structural multi-line comment headers
        header = ""
        if remaining_code.startswith("#"):
            split_content = remaining_code.split("\n", 2)
            if len(split_content) >= 2 and split_content[1].startswith("#"):
                header = f"{split_content[0]}\n{split_content[1]}\n\n"
                remaining_code = split_content[2].lstrip() if len(split_content) > 2 else ""
            else:
                first_line = remaining_code.split("\n", 1)[0]
                if "/" in first_line or "\\" in first_line:
                    header = first_line + "\n\n"
                    remaining_code = remaining_code.split("\n", 1)[1].lstrip()

        new_imports_block = "\n".join(unique_imports.keys())
        
        # Assemble file payload seamlessly
        if new_imports_block:
            final_content = f"{header}{new_imports_block}\n\n{remaining_code}".strip() + "\n"
        else:
            final_content = f"{header}{remaining_code}".strip() + "\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_content)
            
        print(f"Cleaned and optimized imports: {relative_path}")

    except SyntaxError:
        print(f"Skipped (Syntax Error): {relative_path}")
    except Exception as e:
        print(f"Error processing {relative_path}: {e}")

def run_import_cleaner():
    root_path = find_project_root(Path(__file__))
    print(f"Targeting project root: {root_path}")

    for py_file in root_path.rglob("*.py"):
        if should_skip(py_file.relative_to(root_path)):
            continue
        clean_file_imports(py_file, root_path)

if __name__ == "__main__":
    run_import_cleaner()