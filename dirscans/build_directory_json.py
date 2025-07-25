#!/usr/bin/env python3
"""
Directory JSON Builder

This script walks through a directory recursively and creates a JSON file
containing information about each path, including the number of files
and total size of files in each directory.

Usage:
    python build_directory_json.py <directory_path>
"""

import os
import sys
import json
import glob
import argparse
from pathlib import Path
from datetime import datetime

def get_directory_info(directory_path):
    """
    Walk through directory and collect information about each path.
    
    Args:
        directory_path (str): Path to the directory to analyze
        
    Returns:
        dict: Dictionary with path information
    """
    result = {}
    
    try:
        for root, dirs, files in os.walk(directory_path):
            # Count files in current directory
            file_count = len(files)
            
            # Calculate total size of files in current directory
            total_size = 0
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                except (OSError, IOError):
                    # Skip files that can't be accessed
                    continue
            
            # Store information for this path
            result[root] = {
                "file_count": file_count,
                "total_size_bytes": total_size,
            }
    
    except PermissionError:
        print(f"Error: Permission denied accessing {directory_path}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Directory {directory_path} not found")
        sys.exit(1)
    
    return result


def main():
    """Main function to parse arguments and generate JSON file."""
    parser = argparse.ArgumentParser(
        description="Analyze directory structure and create JSON report"
    )
    parser.add_argument(
        "directory",
        help="Directory path to analyze"
    )
    
    args = parser.parse_args()
    
    # Validate directory exists
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a valid directory")
        sys.exit(1)
    
    # Get directory information
    print(f"Analyzing directory: {args.directory}")
    directory_info = get_directory_info(args.directory)
    
    # Create output JSON file in the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # use the path to analyze as the name of the output file
    # prepand with YYYMMDD_HHMMSS
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(script_dir, timestamp + "_" + args.directory.replace('/', '_').replace('\\', '_').replace(':', '_') + ".json")
    # Check for existing files with same directory name but different timestamp
    existing_files = glob.glob(os.path.join(script_dir, "*_" + args.directory.replace('/', '_').replace('\\', '_').replace(':', '_') + ".json"))
    if existing_files:
        # delete the file
        for file in existing_files:
            os.remove(file)
    
    # Add metadata to the result
    result = {
        "analyzed_directory": os.path.abspath(args.directory),
        "total_paths": len(directory_info),
        "paths": directory_info
    }
    
    # Write JSON file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"JSON file created successfully: {output_file}")
        print(f"Total paths analyzed: {len(directory_info)}")
        
        # Calculate and display summary
        total_files = sum(info["file_count"] for info in directory_info.values())
        total_size = sum(info["total_size_bytes"] for info in directory_info.values())
        
        print(f"Total files: {total_files}")
        print(f"Total size: {total_size:,} bytes ({total_size / (1024 * 1024):.2f} MB)")
        
    except IOError as e:
        print(f"Error writing JSON file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 