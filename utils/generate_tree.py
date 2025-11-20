
"""
Generate and print a Unicode tree view of a directory structure.

This module provides a single public function, build_tree(), which performs a
depth-first traversal of a directory and prints a visual representation similar
to the Unix `tree` command using box-drawing characters.

Key behaviors and comments:
- Traversal: Depth-first, printing each directory before its children.
- Ordering: Uses os.listdir(); output is unsorted and includes hidden files.
- Output: Prints to stdout; returns None (side-effect function).
- Connectors:
    - '├── ' marks intermediate siblings within a directory.
    - '└── ' marks the last item within a directory.
    - '│   ' continues vertical guides for subsequent siblings.
    - '    ' (spaces) pads when the current branch is the last item.
- Recursion: indent accumulates guides/spaces to keep alignment consistent.
- Robustness: No internal try/except; callers may wrap to handle permission or
    missing-path errors for large or protected trees.

Potential exceptions:
- FileNotFoundError: start_path does not exist.
- NotADirectoryError: start_path is not a directory.
- PermissionError: Insufficient rights to list a directory.
- OSError: Other OS-related errors during traversal.

Performance notes:
- Time complexity O(N) for N filesystem entries visited.
- Recursion depth equals the maximum directory nesting; very deep trees can hit
    Python’s recursion limit.

Example:
"""

"""
Recursively print a directory tree rooted at start_path using Unicode box-drawing characters.

Args:
        start_path (str | os.PathLike): The root directory from which to begin
                traversal and printing.
        indent (str): Internal-use indentation prefix that carries the visual guides
                between recursive calls. Leave as the default when calling externally.

Detailed behavior and comments:
- Enumerates entries with os.listdir(start_path) and iterates in that order.
- For each entry:
    - Determines the connector:
        - '└── ' if the entry is the last item in the current directory.
        - '├── ' otherwise.
    - Prints the connector followed by the entry name.
- If an entry is a directory:
    - Chooses the next indentation:
        - '    ' (four spaces) if the current entry is the last item (no vertical guide).
        - '│   ' if there are remaining siblings (maintains a vertical guide).
    - Recursively processes the subdirectory with the updated indent.

Returns:
        None. All results are written directly to stdout.

Raises:
        FileNotFoundError: If start_path does not exist.
        NotADirectoryError: If start_path is a file instead of a directory.
        PermissionError: If a directory cannot be listed due to permissions.
        OSError: For other filesystem-related errors encountered.

Notes:
- Output includes hidden files and directories (e.g., names starting with '.').
- Ensure your terminal supports Unicode for the box-drawing characters.
- For very large trees or deep nesting, consider adding error handling, sorting
    (e.g., by name), or limiting depth to improve readability and robustness.
"""


import os

def build_tree(start_path, indent=""):
    items = os.listdir(start_path)
    for i, item in enumerate(items):
        path = os.path.join(start_path, item)
        connector = "└── " if i == len(items)-1 else "├── "
        print(indent + connector + item)
        if os.path.isdir(path):
            extension = "    " if i == len(items)-1 else "│   "
            build_tree(path, indent + extension)

build_tree(".")
