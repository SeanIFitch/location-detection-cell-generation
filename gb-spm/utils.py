import os


def absolute_path(filename):
    # Get the directory of the currently running script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Append the filename to the script directory
    file_path = os.path.join(script_dir, filename)

    return file_path
