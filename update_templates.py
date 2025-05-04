#!/usr/bin/env python
import os
import re
from pathlib import Path

def process_file(file_path):
    """Replace LDCS18 with ldcs in the given file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Count occurrences
        count = content.count('LDCS18')
        if count > 0:
            print(f"Found {count} occurrences in {file_path}")
            
            # Replace LDCS18 with ldcs
            updated_content = content.replace('LDCS18', 'ldcs')
            
            # Write back to the file if changes were made
            if content != updated_content:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(updated_content)
                print(f"Updated: {file_path}")
            else:
                print(f"No changes made despite finding occurrences: {file_path}")
        else:
            print(f"No occurrences found in: {file_path}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def process_directory(dir_path, extensions=None):
    """Recursively process all files in the directory with given extensions."""
    if extensions is None:
        extensions = ['.html', '.py', '.md', '.txt', '.sh', '.bat', '.service', '.conf']
    
    print(f"Processing directory: {dir_path}")
    
    if not os.path.exists(dir_path):
        print(f"Directory doesn't exist: {dir_path}")
        return
        
    for root, _, files in os.walk(dir_path):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in extensions:
                process_file(file_path)

# Process the main directories
directories_to_process = [
    'xrayapp/templates',
    'ldcs_project',
]

for directory in directories_to_process:
    process_directory(directory)

# Process specific files
individual_files = [
    'README.md',
    'DEPLOYMENT.md',
    'deploy_to_production.sh',
    'gunicorn_config.py',
    'run_linux.sh',
    'run_windows.bat',
    'setup.py',
    'xrayapp/templates/xrayapp/home.html',
    'xrayapp/templates/xrayapp/base.html',
    'xrayapp/templates/xrayapp/results.html',
]

for file in individual_files:
    if os.path.exists(file):
        process_file(file)
    else:
        print(f"File doesn't exist: {file}")

print("Template update complete!") 