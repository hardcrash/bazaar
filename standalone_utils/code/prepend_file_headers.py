# standalone_utils/code/prepend_file_headers.py
#
# Purpose: Recursively iterates through the project workspace to prepend a file 
# path comment and a short structural description to all project-owned Python 
# files while ignoring external dependencies.

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

def add_file_path_header():
    root_path = find_project_root(Path(__file__))
    print(f"Targeting project root: {root_path}")
    
    for py_file in root_path.rglob("*.py"):
        # Calculate the relative path from the project root
        relative_path = py_file.relative_to(root_path)
        
        # Skip dependency directories and the standalone_utils folder entirely
        if should_skip(relative_path):
            continue
            
        header_comment = f"# {relative_path}\n"
        
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                
            if content.startswith(header_comment):
                continue
                
            if content.strip() == "":
                new_content = header_comment
            else:
                new_content = f"{header_comment}\n{content}"
                
            with open(py_file, "w", encoding="utf-8") as f:
                f.write(new_content)
                
            print(f"Updated header: {relative_path}")
            
        except Exception as e:
            print(f"Error processing {relative_path}: {e}")

if __name__ == "__main__":
    add_file_path_header()