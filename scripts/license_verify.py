# -----------------------------------------------------------------------------
# Copyright (c) Equinor ASA. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# -----------------------------------------------------------------------------

"""Verify that all *.py files have a license header in the file."""


import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

PY_LICENSE_HEADER = """# -----------------------------------------------------------------------------
# Copyright (c) Equinor ASA. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# -----------------------------------------------------------------------------
"""

env_folders = [
    os.path.join(ROOT_DIR, ".env"),
    os.path.join(ROOT_DIR, ".tox"),
]


def contains_header(text):
    """Returns whether the default header is in the passed text"""
    return PY_LICENSE_HEADER in text


def get_files_without_header():
    """Get python files that don't have the default header"""
    files_without_header = []
    for current_dir, _, files in os.walk(ROOT_DIR):
        # skip folders generated by virtual env
        if any(d for d in env_folders if d in current_dir):
            continue

        for a_file in files:
            if a_file.endswith(".py"):
                cur_file_path = os.path.join(current_dir, a_file)
                with open(cur_file_path, "r", encoding="UTF-8") as file:
                    file_text = file.read()

                if len(file_text) > 0 and not contains_header(file_text):
                    files_without_header.append((cur_file_path, file_text))
    return files_without_header


def main():
    """Main function"""
    files_without_header = [file_path for file_path, _ in get_files_without_header()]

    if files_without_header:
        print(
            "Error: The following files don't have the required license headers:", file=sys.stderr
        )
        print("\n".join(files_without_header), file=sys.stderr)
        print(
            "Error: {} file(s) found without license headers.".format(len(files_without_header)),
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        pass


if __name__ == "__main__":
    main()
