import os
import ast
import sys
import importlib.util
import pkg_resources

# List of Python standard library modules (Python 3.9+)
stdlib_modules = set(sys.builtin_module_names)
stdlib_modules.update({
    "abc", "argparse", "asyncio", "base64", "binascii", "bisect", "calendar",
    "collections", "concurrent", "contextlib", "copy", "csv", "ctypes", "datetime",
    "decimal", "difflib", "email", "enum", "functools", "fractions", "getopt", 
    "getpass", "glob", "gzip", "hashlib", "heapq", "hmac", "http", "importlib",
    "inspect", "io", "itertools", "json", "logging", "math", "multiprocessing",
    "numbers", "operator", "os", "pathlib", "pickle", "platform", "plistlib",
    "pprint", "queue", "random", "re", "shutil", "signal", "socket", "sqlite3",
    "statistics", "string", "struct", "subprocess", "sysconfig", "tempfile", 
    "textwrap", "threading", "time", "timeit", "traceback", "typing", "unittest",
    "uuid", "warnings", "weakref", "xml", "zipfile", "zoneinfo"
})

project_dir = "./oceanicospy"  # 👈 change if needed
imports = set()

# --- Crawl all Python files and collect imports ---
for root, _, files in os.walk(project_dir):
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=filepath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.add(alias.name.split('.')[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.add(node.module.split('.')[0])
            except SyntaxError:
                pass

# --- Filter out stdlib + internal package imports ---
filtered = []
for mod in sorted(imports):
    if mod in stdlib_modules:
        continue
    if mod == "oceanicospy":  # internal package
        continue
    filtered.append(mod)

# --- Try resolving to installed package names ---
requirements = []
for mod in filtered:
    spec = importlib.util.find_spec(mod)
    if spec is None:
        requirements.append(mod)  # unknown, keep as-is
    else:
        try:
            dist = pkg_resources.get_distribution(mod)
            requirements.append(f"{dist.project_name}>={dist.version}")
        except Exception:
            requirements.append(mod)

requirements = sorted(set(requirements))

# --- Save to file ---
with open("requirements_runtime.txt", "w") as f:
    f.write("\n".join(requirements))

print("✅ Runtime dependencies written to requirements_runtime.txt")
print("\n".join(requirements))
