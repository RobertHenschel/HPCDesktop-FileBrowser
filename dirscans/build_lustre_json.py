#!/usr/bin/env python3
"""
Lustre File Metadata Scanner
Gathers comprehensive file metadata using both standard Linux tools and Lustre lfs commands.
Includes checkpoint/resume functionality to resist interruption.
"""

import os
import sys
import json
import stat
import pwd
import grp
import subprocess
import argparse
import sqlite3
import shutil
import time
from pathlib import Path
from datetime import datetime
import hashlib


def run_command(cmd, ignore_errors=True):
    """Run a shell command and return the output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return result.stdout.strip()
        elif not ignore_errors:
            return f"Error: {result.stderr.strip()}"
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        return None if ignore_errors else f"Exception: {str(e)}"


def get_file_hash(filepath, algorithm='md5', chunk_size=8192):
    """Calculate file hash for small files (under 100MB)."""
    try:
        file_size = os.path.getsize(filepath)
        if file_size > 100 * 1024 * 1024:  # Skip files larger than 100MB
            return None
        
        hash_obj = hashlib.new(algorithm)
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except (IOError, OSError):
        return None


class CheckpointManager:
    """Manages checkpoint/resume functionality for the scanner."""
    
    def __init__(self, output_file, directory_path):
        # Create temp directory name based on output file or default
        if output_file:
            base_name = os.path.splitext(os.path.basename(output_file))[0]
        else:
            base_name = f"lustre_scan_{os.path.basename(os.path.abspath(directory_path))}"
        
        self.temp_dir = f".{base_name}_checkpoint"
        self.progress_file = os.path.join(self.temp_dir, "scan_progress.json")
        self.processed_files_file = os.path.join(self.temp_dir, "processed_files.txt")
        self.partial_results_file = os.path.join(self.temp_dir, "results_partial.json")
        
        self.processed_files = set()
        self.restart_count = 0
        self.start_time = time.time()
        self.initial_start_time = self.start_time
        
    def setup_checkpoint_dir(self):
        """Create checkpoint directory if it doesn't exist."""
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
            print(f"Created checkpoint directory: {self.temp_dir}", file=sys.stderr)
        
    def load_existing_progress(self):
        """Load existing progress if resuming from a checkpoint."""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    progress_data = json.load(f)
                
                self.restart_count = progress_data.get('restart_count', 0) + 1
                self.initial_start_time = progress_data.get('initial_start_time', time.time())
                
                print(f"Resuming scan (restart #{self.restart_count})", file=sys.stderr)
                print(f"Original scan started: {datetime.fromtimestamp(self.initial_start_time).isoformat()}", file=sys.stderr)
                
                return progress_data
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load progress file: {e}", file=sys.stderr)
                return None
        return None
    
    def load_processed_files(self):
        """Load list of already processed files."""
        if os.path.exists(self.processed_files_file):
            try:
                with open(self.processed_files_file, 'r') as f:
                    self.processed_files = set(line.strip() for line in f if line.strip())
                print(f"Loaded {len(self.processed_files)} already processed files", file=sys.stderr)
            except IOError as e:
                print(f"Warning: Could not load processed files list: {e}", file=sys.stderr)
    
    def load_partial_results(self):
        """Load partial results from previous run."""
        if os.path.exists(self.partial_results_file):
            try:
                with open(self.partial_results_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load partial results: {e}", file=sys.stderr)
        return None
    
    def save_progress(self, directory_path, total_files, processed_count):
        """Save current progress to checkpoint."""
        progress_data = {
            'directory': directory_path,
            'total_files': total_files,
            'processed_count': processed_count,
            'restart_count': self.restart_count,
            'current_time': time.time(),
            'initial_start_time': self.initial_start_time,
            'elapsed_time': time.time() - self.initial_start_time
        }
        
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save progress: {e}", file=sys.stderr)
    
    def mark_file_processed(self, filepath):
        """Mark a file as processed."""
        self.processed_files.add(filepath)
        try:
            with open(self.processed_files_file, 'a') as f:
                f.write(f"{filepath}\n")
        except IOError as e:
            print(f"Warning: Could not update processed files list: {e}", file=sys.stderr)
    
    def save_partial_results(self, results):
        """Save partial results to checkpoint."""
        try:
            with open(self.partial_results_file, 'w') as f:
                json.dump(results, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save partial results: {e}", file=sys.stderr)
    
    def is_file_processed(self, filepath):
        """Check if a file has already been processed."""
        return filepath in self.processed_files
    
    def cleanup(self):
        """Remove checkpoint directory and all temporary files."""
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"Cleaned up checkpoint directory: {self.temp_dir}", file=sys.stderr)
            except OSError as e:
                print(f"Warning: Could not clean up checkpoint directory: {e}", file=sys.stderr)
    
    def get_scan_stats(self):
        """Get scan timing and restart statistics."""
        total_elapsed = time.time() - self.initial_start_time
        return {
            'restart_count': self.restart_count,
            'total_elapsed_seconds': total_elapsed,
            'total_elapsed_formatted': format_duration(total_elapsed),
            'initial_start_time': self.initial_start_time,
            'initial_start_time_iso': datetime.fromtimestamp(self.initial_start_time).isoformat()
        }


def format_duration(seconds):
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


def get_standard_metadata(filepath):
    """Gather standard Linux file metadata."""
    try:
        file_stat = os.stat(filepath)
        
        # Get file type
        file_mode = file_stat.st_mode
        if stat.S_ISREG(file_mode):
            file_type = 'regular'
        elif stat.S_ISDIR(file_mode):
            file_type = 'directory'
        elif stat.S_ISLNK(file_mode):
            file_type = 'symlink'
        elif stat.S_ISBLK(file_mode):
            file_type = 'block_device'
        elif stat.S_ISCHR(file_mode):
            file_type = 'character_device'
        elif stat.S_ISFIFO(file_mode):
            file_type = 'fifo'
        elif stat.S_ISSOCK(file_mode):
            file_type = 'socket'
        else:
            file_type = 'unknown'
        
        # Get user and group names
        try:
            username = pwd.getpwuid(file_stat.st_uid).pw_name
        except KeyError:
            username = str(file_stat.st_uid)
        
        try:
            groupname = grp.getgrgid(file_stat.st_gid).gr_name
        except KeyError:
            groupname = str(file_stat.st_gid)
        
        metadata = {
            'path': filepath,
            'basename': os.path.basename(filepath),
            'size_bytes': file_stat.st_size,
            'size_human': format_bytes(file_stat.st_size),
            'type': file_type,
            'permissions': {
                'octal': oct(file_stat.st_mode)[-3:],
                'symbolic': stat.filemode(file_stat.st_mode),
                'user_readable': bool(file_stat.st_mode & stat.S_IRUSR),
                'user_writable': bool(file_stat.st_mode & stat.S_IWUSR),
                'user_executable': bool(file_stat.st_mode & stat.S_IXUSR),
                'group_readable': bool(file_stat.st_mode & stat.S_IRGRP),
                'group_writable': bool(file_stat.st_mode & stat.S_IWGRP),
                'group_executable': bool(file_stat.st_mode & stat.S_IXGRP),
                'other_readable': bool(file_stat.st_mode & stat.S_IROTH),
                'other_writable': bool(file_stat.st_mode & stat.S_IWOTH),
                'other_executable': bool(file_stat.st_mode & stat.S_IXOTH),
                'setuid': bool(file_stat.st_mode & stat.S_ISUID),
                'setgid': bool(file_stat.st_mode & stat.S_ISGID),
                'sticky': bool(file_stat.st_mode & stat.S_ISVTX)
            },
            'ownership': {
                'uid': file_stat.st_uid,
                'gid': file_stat.st_gid,
                'username': username,
                'groupname': groupname
            },
            'timestamps': {
                'access_time': file_stat.st_atime,
                'modify_time': file_stat.st_mtime,
                'change_time': file_stat.st_ctime,
                'access_time_iso': datetime.fromtimestamp(file_stat.st_atime).isoformat(),
                'modify_time_iso': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                'change_time_iso': datetime.fromtimestamp(file_stat.st_ctime).isoformat()
            },
            'inode': {
                'number': file_stat.st_ino,
                'device': file_stat.st_dev,
                'links': file_stat.st_nlink
            }
        }
        
        # Add symlink target if it's a symlink
        if file_type == 'symlink':
            try:
                metadata['symlink_target'] = os.readlink(filepath)
            except OSError:
                metadata['symlink_target'] = None
        
        # Add file hash for small regular files
        if file_type == 'regular' and file_stat.st_size > 0:
            metadata['checksums'] = {
                'md5': get_file_hash(filepath, 'md5'),
                'sha1': get_file_hash(filepath, 'sha1'),
                'sha256': get_file_hash(filepath, 'sha256')
            }
        
        return metadata
        
    except (OSError, IOError) as e:
        return {'error': f"Could not get standard metadata: {str(e)}"}


def get_lustre_metadata(filepath):
    """Gather Lustre-specific file metadata using lfs commands."""
    lustre_data = {}
    
    # Get Lustre stripe information
    stripe_info = run_command(f"lfs getstripe -v '{filepath}'")
    if stripe_info:
        lustre_data['stripe_info_raw'] = stripe_info
        
        # Parse stripe information
        try:
            stripe_data = {}
            lines = stripe_info.split('\n')
            for line in lines:
                line = line.strip()
                if 'stripe_count:' in line:
                    stripe_data['stripe_count'] = int(line.split(':')[1].strip())
                elif 'stripe_size:' in line:
                    stripe_data['stripe_size'] = int(line.split(':')[1].strip())
                elif 'stripe_offset:' in line:
                    stripe_data['stripe_offset'] = int(line.split(':')[1].strip())
                elif 'pool:' in line and 'pool:' != line.split(':')[1].strip():
                    stripe_data['pool'] = line.split(':')[1].strip()
            
            if stripe_data:
                lustre_data['stripe_parsed'] = stripe_data
        except (ValueError, IndexError):
            pass
    
    # Get detailed stripe layout
    layout_info = run_command(f"lfs getstripe -y '{filepath}'")
    if layout_info:
        try:
            import yaml
            lustre_data['layout_yaml'] = yaml.safe_load(layout_info)
        except:
            lustre_data['layout_raw'] = layout_info
    
    # Get OST (Object Storage Target) information
    ost_info = run_command(f"lfs getstripe -O '{filepath}'")
    if ost_info:
        lustre_data['ost_indices'] = [int(x.strip()) for x in ost_info.split() if x.strip().isdigit()]
    
    # Get file FID (File Identifier)
    fid_info = run_command(f"lfs path2fid '{filepath}'")
    if fid_info:
        lustre_data['fid'] = fid_info
    
    # Get component information (for composite layouts)
    comp_info = run_command(f"lfs getstripe --component-count '{filepath}'")
    if comp_info and comp_info.isdigit():
        lustre_data['component_count'] = int(comp_info)
        
        # Get information for each component
        components = []
        for i in range(int(comp_info)):
            comp_detail = run_command(f"lfs getstripe --component-id {i} '{filepath}'")
            if comp_detail:
                components.append({
                    'component_id': i,
                    'info': comp_detail
                })
        if components:
            lustre_data['components'] = components
    
    # Get Lustre filesystem information
    fs_info = run_command(f"lfs df '{filepath}'")
    if fs_info:
        lustre_data['filesystem_info'] = fs_info
    
    # Get quota information if available
    quota_info = run_command(f"lfs quota -u $(id -u) '{filepath}'")
    if quota_info and 'not supported' not in quota_info.lower():
        lustre_data['user_quota'] = quota_info
    
    return lustre_data


def get_extended_attributes(filepath):
    """Get extended attributes if available."""
    xattr_data = {}
    
    # Get all extended attributes
    xattr_list = run_command(f"getfattr -d '{filepath}' 2>/dev/null")
    if xattr_list:
        xattr_data['all_attributes'] = xattr_list
    
    # Get security attributes
    security_attrs = run_command(f"getfattr -n security.selinux '{filepath}' 2>/dev/null")
    if security_attrs:
        xattr_data['selinux'] = security_attrs
    
    return xattr_data


def get_acl_info(filepath):
    """Get Access Control List information."""
    acl_data = {}
    
    # Get POSIX ACLs
    posix_acl = run_command(f"getfacl '{filepath}' 2>/dev/null")
    if posix_acl and 'Operation not supported' not in posix_acl:
        acl_data['posix_acl'] = posix_acl
    
    return acl_data


def format_bytes(bytes_value):
    """Convert bytes to human readable format."""
    if bytes_value == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    size = float(bytes_value)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"


def create_database_schema(cursor):
    """Create SQLite database schema for file metadata."""
    
    # Scan info table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_info (
            id INTEGER PRIMARY KEY,
            directory TEXT NOT NULL,
            scan_time TEXT NOT NULL,
            scan_completed TEXT,
            hostname TEXT,
            lustre_version TEXT,
            total_files INTEGER,
            restart_count INTEGER,
            total_elapsed_seconds REAL,
            initial_start_time TEXT,
            recursive BOOLEAN
        )
    ''')
    
    # Main files table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            scan_id INTEGER,
            scan_order INTEGER,
            path TEXT NOT NULL,
            basename TEXT,
            size_bytes INTEGER,
            size_human TEXT,
            file_type TEXT,
            symlink_target TEXT,
            error_message TEXT,
            FOREIGN KEY (scan_id) REFERENCES scan_info (id)
        )
    ''')
    
    # File permissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_permissions (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            octal TEXT,
            symbolic TEXT,
            user_readable BOOLEAN,
            user_writable BOOLEAN,
            user_executable BOOLEAN,
            group_readable BOOLEAN,
            group_writable BOOLEAN,
            group_executable BOOLEAN,
            other_readable BOOLEAN,
            other_writable BOOLEAN,
            other_executable BOOLEAN,
            setuid BOOLEAN,
            setgid BOOLEAN,
            sticky BOOLEAN,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')
    
    # File ownership table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_ownership (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            uid INTEGER,
            gid INTEGER,
            username TEXT,
            groupname TEXT,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')
    
    # File timestamps table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_timestamps (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            access_time REAL,
            modify_time REAL,
            change_time REAL,
            access_time_iso TEXT,
            modify_time_iso TEXT,
            change_time_iso TEXT,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')
    
    # File inode table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_inodes (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            inode_number INTEGER,
            device INTEGER,
            links INTEGER,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')
    
    # File checksums table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_checksums (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            md5 TEXT,
            sha1 TEXT,
            sha256 TEXT,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')
    
    # Lustre metadata table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lustre_metadata (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            stripe_info_raw TEXT,
            stripe_count INTEGER,
            stripe_size INTEGER,
            stripe_offset INTEGER,
            pool TEXT,
            layout_raw TEXT,
            layout_yaml TEXT,
            ost_indices TEXT,
            fid TEXT,
            component_count INTEGER,
            components TEXT,
            filesystem_info TEXT,
            user_quota TEXT,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')
    
    # Extended attributes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS extended_attributes (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            all_attributes TEXT,
            selinux TEXT,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')
    
    # ACL info table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS acl_info (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            posix_acl TEXT,
            FOREIGN KEY (file_id) REFERENCES files (id)
        )
    ''')


def insert_scan_data_to_db(cursor, results):
    """Insert scan results into SQLite database."""
    
    # Insert scan info
    scan_info = results['scan_info']
    checkpoint_stats = scan_info.get('checkpoint_stats', {})
    cursor.execute('''
        INSERT INTO scan_info (directory, scan_time, scan_completed, hostname, lustre_version, total_files, restart_count, total_elapsed_seconds, initial_start_time, recursive)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        scan_info.get('directory'),
        scan_info.get('scan_time'),
        scan_info.get('scan_completed'),
        scan_info.get('hostname'),
        scan_info.get('lustre_version'),
        scan_info.get('total_files'),
        checkpoint_stats.get('restart_count'),
        checkpoint_stats.get('total_elapsed_seconds'),
        scan_info.get('initial_start_time'),
        scan_info.get('recursive')
    ))
    
    scan_id = cursor.lastrowid
    
    # Insert file data
    for file_data in results['files']:
        std_meta = file_data.get('standard_metadata', {})
        
        # Insert main file record
        cursor.execute('''
            INSERT INTO files (scan_id, scan_order, path, basename, size_bytes, size_human, file_type, symlink_target, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan_id,
            file_data.get('scan_order'),
            std_meta.get('path'),
            std_meta.get('basename'),
            std_meta.get('size_bytes'),
            std_meta.get('size_human'),
            std_meta.get('type'),
            std_meta.get('symlink_target'),
            std_meta.get('error')
        ))
        
        file_id = cursor.lastrowid
        
        # Insert permissions
        perms = std_meta.get('permissions', {})
        if perms:
            cursor.execute('''
                INSERT INTO file_permissions (file_id, octal, symbolic, user_readable, user_writable, user_executable,
                                            group_readable, group_writable, group_executable,
                                            other_readable, other_writable, other_executable,
                                            setuid, setgid, sticky)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_id, perms.get('octal'), perms.get('symbolic'),
                perms.get('user_readable'), perms.get('user_writable'), perms.get('user_executable'),
                perms.get('group_readable'), perms.get('group_writable'), perms.get('group_executable'),
                perms.get('other_readable'), perms.get('other_writable'), perms.get('other_executable'),
                perms.get('setuid'), perms.get('setgid'), perms.get('sticky')
            ))
        
        # Insert ownership
        ownership = std_meta.get('ownership', {})
        if ownership:
            cursor.execute('''
                INSERT INTO file_ownership (file_id, uid, gid, username, groupname)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                file_id, ownership.get('uid'), ownership.get('gid'),
                ownership.get('username'), ownership.get('groupname')
            ))
        
        # Insert timestamps
        timestamps = std_meta.get('timestamps', {})
        if timestamps:
            cursor.execute('''
                INSERT INTO file_timestamps (file_id, access_time, modify_time, change_time,
                                           access_time_iso, modify_time_iso, change_time_iso)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_id, timestamps.get('access_time'), timestamps.get('modify_time'), timestamps.get('change_time'),
                timestamps.get('access_time_iso'), timestamps.get('modify_time_iso'), timestamps.get('change_time_iso')
            ))
        
        # Insert inode info
        inode = std_meta.get('inode', {})
        if inode:
            cursor.execute('''
                INSERT INTO file_inodes (file_id, inode_number, device, links)
                VALUES (?, ?, ?, ?)
            ''', (
                file_id, inode.get('number'), inode.get('device'), inode.get('links')
            ))
        
        # Insert checksums
        checksums = std_meta.get('checksums', {})
        if checksums:
            cursor.execute('''
                INSERT INTO file_checksums (file_id, md5, sha1, sha256)
                VALUES (?, ?, ?, ?)
            ''', (
                file_id, checksums.get('md5'), checksums.get('sha1'), checksums.get('sha256')
            ))
        
        # Insert Lustre metadata
        lustre_meta = file_data.get('lustre_metadata', {})
        if lustre_meta:
            stripe_parsed = lustre_meta.get('stripe_parsed', {})
            cursor.execute('''
                INSERT INTO lustre_metadata (file_id, stripe_info_raw, stripe_count, stripe_size, stripe_offset, pool,
                                           layout_raw, layout_yaml, ost_indices, fid, component_count, components,
                                           filesystem_info, user_quota)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_id,
                lustre_meta.get('stripe_info_raw'),
                stripe_parsed.get('stripe_count'),
                stripe_parsed.get('stripe_size'),
                stripe_parsed.get('stripe_offset'),
                stripe_parsed.get('pool'),
                lustre_meta.get('layout_raw'),
                json.dumps(lustre_meta.get('layout_yaml')) if lustre_meta.get('layout_yaml') else None,
                json.dumps(lustre_meta.get('ost_indices')) if lustre_meta.get('ost_indices') else None,
                lustre_meta.get('fid'),
                lustre_meta.get('component_count'),
                json.dumps(lustre_meta.get('components')) if lustre_meta.get('components') else None,
                lustre_meta.get('filesystem_info'),
                lustre_meta.get('user_quota')
            ))
        
        # Insert extended attributes
        xattr = file_data.get('extended_attributes', {})
        if xattr:
            cursor.execute('''
                INSERT INTO extended_attributes (file_id, all_attributes, selinux)
                VALUES (?, ?, ?)
            ''', (
                file_id, xattr.get('all_attributes'), xattr.get('selinux')
            ))
        
        # Insert ACL info
        acl = file_data.get('acl_info', {})
        if acl:
            cursor.execute('''
                INSERT INTO acl_info (file_id, posix_acl)
                VALUES (?, ?)
            ''', (
                file_id, acl.get('posix_acl')
            ))


def create_database_schema_json(schema_file):
    """Create a JSON file describing the database schema."""
    schema = {
        "database_schema": {
            "description": "SQLite database schema for Lustre file metadata scanner",
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "tables": {
                "scan_info": {
                    "description": "Information about the directory scan",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True, "description": "Unique scan identifier"},
                        "directory": {"type": "TEXT", "description": "Directory that was scanned"},
                        "scan_time": {"type": "TEXT", "description": "ISO timestamp when scan started"},
                        "scan_completed": {"type": "TEXT", "description": "ISO timestamp when scan completed"},
                        "hostname": {"type": "TEXT", "description": "Hostname where scan was performed"},
                        "lustre_version": {"type": "TEXT", "description": "Version of Lustre tools"},
                        "total_files": {"type": "INTEGER", "description": "Total number of files scanned"},
                        "restart_count": {"type": "INTEGER", "description": "Number of times scan was restarted from checkpoint"},
                        "total_elapsed_seconds": {"type": "REAL", "description": "Total elapsed time for entire scan in seconds"},
                        "initial_start_time": {"type": "TEXT", "description": "ISO timestamp when scan was first started"},
                        "recursive": {"type": "BOOLEAN", "description": "Whether the scan was performed recursively"}
                    }
                },
                "files": {
                    "description": "Basic file information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True, "description": "Unique file record identifier"},
                        "scan_id": {"type": "INTEGER", "foreign_key": "scan_info.id", "description": "Reference to scan"},
                        "scan_order": {"type": "INTEGER", "description": "Order in which file was scanned"},
                        "path": {"type": "TEXT", "description": "Full path to the file"},
                        "basename": {"type": "TEXT", "description": "File basename"},
                        "size_bytes": {"type": "INTEGER", "description": "File size in bytes"},
                        "size_human": {"type": "TEXT", "description": "Human-readable file size"},
                        "file_type": {"type": "TEXT", "description": "File type (regular, directory, symlink, etc.)"},
                        "symlink_target": {"type": "TEXT", "description": "Target of symlink if applicable"},
                        "error_message": {"type": "TEXT", "description": "Error message if metadata collection failed"}
                    }
                },
                "file_permissions": {
                    "description": "File permission information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "file_id": {"type": "INTEGER", "foreign_key": "files.id"},
                        "octal": {"type": "TEXT", "description": "Octal permission representation"},
                        "symbolic": {"type": "TEXT", "description": "Symbolic permission representation"},
                        "user_readable": {"type": "BOOLEAN", "description": "User read permission"},
                        "user_writable": {"type": "BOOLEAN", "description": "User write permission"},
                        "user_executable": {"type": "BOOLEAN", "description": "User execute permission"},
                        "group_readable": {"type": "BOOLEAN", "description": "Group read permission"},
                        "group_writable": {"type": "BOOLEAN", "description": "Group write permission"},
                        "group_executable": {"type": "BOOLEAN", "description": "Group execute permission"},
                        "other_readable": {"type": "BOOLEAN", "description": "Other read permission"},
                        "other_writable": {"type": "BOOLEAN", "description": "Other write permission"},
                        "other_executable": {"type": "BOOLEAN", "description": "Other execute permission"},
                        "setuid": {"type": "BOOLEAN", "description": "Set user ID bit"},
                        "setgid": {"type": "BOOLEAN", "description": "Set group ID bit"},
                        "sticky": {"type": "BOOLEAN", "description": "Sticky bit"}
                    }
                },
                "file_ownership": {
                    "description": "File ownership information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "file_id": {"type": "INTEGER", "foreign_key": "files.id"},
                        "uid": {"type": "INTEGER", "description": "User ID"},
                        "gid": {"type": "INTEGER", "description": "Group ID"},
                        "username": {"type": "TEXT", "description": "Username"},
                        "groupname": {"type": "TEXT", "description": "Group name"}
                    }
                },
                "file_timestamps": {
                    "description": "File timestamp information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "file_id": {"type": "INTEGER", "foreign_key": "files.id"},
                        "access_time": {"type": "REAL", "description": "Access time (Unix timestamp)"},
                        "modify_time": {"type": "REAL", "description": "Modify time (Unix timestamp)"},
                        "change_time": {"type": "REAL", "description": "Change time (Unix timestamp)"},
                        "access_time_iso": {"type": "TEXT", "description": "Access time (ISO format)"},
                        "modify_time_iso": {"type": "TEXT", "description": "Modify time (ISO format)"},
                        "change_time_iso": {"type": "TEXT", "description": "Change time (ISO format)"}
                    }
                },
                "file_inodes": {
                    "description": "File inode information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "file_id": {"type": "INTEGER", "foreign_key": "files.id"},
                        "inode_number": {"type": "INTEGER", "description": "Inode number"},
                        "device": {"type": "INTEGER", "description": "Device ID"},
                        "links": {"type": "INTEGER", "description": "Number of hard links"}
                    }
                },
                "file_checksums": {
                    "description": "File checksum information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "file_id": {"type": "INTEGER", "foreign_key": "files.id"},
                        "md5": {"type": "TEXT", "description": "MD5 hash"},
                        "sha1": {"type": "TEXT", "description": "SHA1 hash"},
                        "sha256": {"type": "TEXT", "description": "SHA256 hash"}
                    }
                },
                "lustre_metadata": {
                    "description": "Lustre-specific file metadata",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "file_id": {"type": "INTEGER", "foreign_key": "files.id"},
                        "stripe_info_raw": {"type": "TEXT", "description": "Raw stripe information output"},
                        "stripe_count": {"type": "INTEGER", "description": "Number of stripes"},
                        "stripe_size": {"type": "INTEGER", "description": "Stripe size in bytes"},
                        "stripe_offset": {"type": "INTEGER", "description": "Stripe offset"},
                        "pool": {"type": "TEXT", "description": "OST pool name"},
                        "layout_raw": {"type": "TEXT", "description": "Raw layout information"},
                        "layout_yaml": {"type": "TEXT", "description": "Layout information in YAML format (JSON encoded)"},
                        "ost_indices": {"type": "TEXT", "description": "OST indices (JSON encoded array)"},
                        "fid": {"type": "TEXT", "description": "Lustre File Identifier"},
                        "component_count": {"type": "INTEGER", "description": "Number of components"},
                        "components": {"type": "TEXT", "description": "Component information (JSON encoded)"},
                        "filesystem_info": {"type": "TEXT", "description": "Filesystem information"},
                        "user_quota": {"type": "TEXT", "description": "User quota information"}
                    }
                },
                "extended_attributes": {
                    "description": "Extended file attributes",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "file_id": {"type": "INTEGER", "foreign_key": "files.id"},
                        "all_attributes": {"type": "TEXT", "description": "All extended attributes"},
                        "selinux": {"type": "TEXT", "description": "SELinux security context"}
                    }
                },
                "acl_info": {
                    "description": "Access Control List information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "file_id": {"type": "INTEGER", "foreign_key": "files.id"},
                        "posix_acl": {"type": "TEXT", "description": "POSIX ACL information"}
                    }
                }
            },
            "usage_examples": {
                "get_all_files_from_scan": "SELECT * FROM files WHERE scan_id = 1;",
                "get_large_files": "SELECT path, size_bytes, size_human FROM files WHERE size_bytes > 1000000 ORDER BY size_bytes DESC;",
                "get_files_with_lustre_info": "SELECT f.path, l.stripe_count, l.stripe_size FROM files f JOIN lustre_metadata l ON f.id = l.file_id;",
                "get_executable_files": "SELECT f.path FROM files f JOIN file_permissions p ON f.id = p.file_id WHERE p.user_executable = 1;",
                "get_recent_files": "SELECT f.path, t.modify_time_iso FROM files f JOIN file_timestamps t ON f.id = t.file_id ORDER BY t.modify_time DESC LIMIT 10;"
            }
        }
    }
    
    with open(schema_file, 'w') as f:
        json.dump(schema, f, indent=2)


def scan_directory(directory_path, checkpoint_manager=None, recursive=False):
    """Scan directory and gather metadata for all files with checkpoint support."""
    if not os.path.isdir(directory_path):
        print(f"Error: '{directory_path}' is not a directory", file=sys.stderr)
        return None
    
    # Initialize or resume results
    if checkpoint_manager:
        existing_results = checkpoint_manager.load_partial_results()
        if existing_results:
            results = existing_results
            print(f"Resuming with {len(results['files'])} files already processed", file=sys.stderr)
        else:
            results = {
                'scan_info': {
                    'directory': os.path.abspath(directory_path),
                    'scan_time': datetime.now().isoformat(),
                    'hostname': run_command('hostname'),
                    'lustre_version': run_command('lfs --version'),
                    'recursive': recursive,
                },
                'files': []
            }
    else:
        results = {
            'scan_info': {
                'directory': os.path.abspath(directory_path),
                'scan_time': datetime.now().isoformat(),
                'hostname': run_command('hostname'),
                'lustre_version': run_command('lfs --version'),
                'recursive': recursive,
            },
            'files': []
        }
    
    try:
        # Get list of files in directory (and subdirectories if recursive)
        entries = []
        if recursive:
            print(f"Recursively scanning {directory_path}...", file=sys.stderr)
            for root, dirs, files in os.walk(directory_path, followlinks=True):
                # Sort directories and files for consistent order across runs
                dirs.sort()
                files.sort()
                for filename in files:
                    item_path = os.path.join(root, filename)
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        entries.append(item_path)
                # Also include symlinks that point to directories
                for dirname in dirs:
                    dir_path = os.path.join(root, dirname)
                    if os.path.islink(dir_path):
                        entries.append(dir_path)
        else:
            # Get list of files in directory only (not subdirectories)
            items = sorted(os.listdir(directory_path))  # Sort for consistent order
            for item in items:
                item_path = os.path.join(directory_path, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    entries.append(item_path)
        
        # Filter out already processed files if resuming
        if checkpoint_manager:
            remaining_entries = [f for f in entries if not checkpoint_manager.is_file_processed(f)]
            already_processed = len(entries) - len(remaining_entries)
            if already_processed > 0:
                print(f"Skipping {already_processed} already processed files", file=sys.stderr)
            entries = remaining_entries
        
        total_files = len(entries) + len(results['files'])  # Include already processed
        scan_scope = "recursively" if recursive else ""
        print(f"Found {len(entries)} files to scan {scan_scope} in {directory_path}", file=sys.stderr)
        if checkpoint_manager:
            print(f"Total files {scan_scope}: {total_files}", file=sys.stderr)
        
        for i, filepath in enumerate(entries, 1):
            current_file_number = len(results['files']) + i
            print(f"Scanning {current_file_number}/{total_files}: {os.path.basename(filepath)}", file=sys.stderr)
            
            file_metadata = {
                'scan_order': current_file_number,
                'standard_metadata': get_standard_metadata(filepath),
                'lustre_metadata': get_lustre_metadata(filepath),
                'extended_attributes': get_extended_attributes(filepath),
                'acl_info': get_acl_info(filepath)
            }
            
            results['files'].append(file_metadata)
            
            # Update checkpoint
            if checkpoint_manager:
                checkpoint_manager.mark_file_processed(filepath)
                
                # Save progress every 10 files or at the end
                if current_file_number % 10 == 0 or i == len(entries):
                    checkpoint_manager.save_progress(directory_path, total_files, current_file_number)
                    checkpoint_manager.save_partial_results(results)
                    print(f"Checkpoint saved ({current_file_number}/{total_files})", file=sys.stderr)
        
        # Update final scan info
        results['scan_info']['total_files'] = total_files
        results['scan_info']['scan_completed'] = datetime.now().isoformat()
        
        # Add checkpoint statistics if available
        if checkpoint_manager:
            scan_stats = checkpoint_manager.get_scan_stats()
            results['scan_info'].update({
                'checkpoint_stats': scan_stats,
                'initial_start_time': scan_stats['initial_start_time_iso']
            })
            print(f"Scan completed after {scan_stats['total_elapsed_formatted']} with {scan_stats['restart_count']} restarts", file=sys.stderr)
        
    except OSError as e:
        print(f"Error scanning directory: {e}", file=sys.stderr)
        return None
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Scan directory and gather comprehensive file metadata including Lustre information',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/directory
  %(prog)s . > metadata.json
  %(prog)s /lustre/project/data --output results.json --db results.db
  %(prog)s /path --output results.json --no-checkpoint  # Disable checkpoint/resume
  %(prog)s /path --recursive --output results.json     # Scan recursively
        """
    )
    
    parser.add_argument('directory', 
                       help='Directory to scan for file metadata')
    parser.add_argument('-o', '--output', 
                       help='Output JSON file (default: stdout)')
    parser.add_argument('--db', '--database',
                       help='Output SQLite database file')
    parser.add_argument('--schema',
                       help='Output JSON schema file (default: <db_name>_schema.json)')
    parser.add_argument('--pretty', action='store_true',
                       help='Pretty-print JSON output')
    parser.add_argument('--no-checkpoint', action='store_true',
                       help='Disable checkpoint/resume functionality')
    parser.add_argument('--cleanup-only', action='store_true',
                       help='Only cleanup checkpoint files and exit')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Recursively scan subdirectories')
    
    args = parser.parse_args()
    
    # Initialize checkpoint manager
    checkpoint_manager = None
    if not args.no_checkpoint:
        checkpoint_manager = CheckpointManager(args.output, args.directory)
        
        # Handle cleanup-only mode
        if args.cleanup_only:
            checkpoint_manager.cleanup()
            print("Checkpoint cleanup completed", file=sys.stderr)
            sys.exit(0)
        
        # Setup checkpoint directory and load existing progress
        checkpoint_manager.setup_checkpoint_dir()
        checkpoint_manager.load_existing_progress()
        checkpoint_manager.load_processed_files()
    
    # Validate directory
    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    # Scan directory
    try:
        results = scan_directory(args.directory, checkpoint_manager, args.recursive)
        if results is None:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nScan interrupted. Checkpoint saved. Run again to resume.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during scan: {e}", file=sys.stderr)
        if checkpoint_manager:
            print(f"Checkpoint files preserved in {checkpoint_manager.temp_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Output JSON results
    json_kwargs = {'indent': 2} if args.pretty else {}
    json_output = json.dumps(results, **json_kwargs)
    
    if args.output:
        try:
            with open(args.output, 'w') as f:
                f.write(json_output)
            print(f"JSON results written to {args.output}", file=sys.stderr)
        except IOError as e:
            print(f"Error writing JSON to {args.output}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(json_output)
    
    # Output to SQLite database
    if args.db:
        try:
            conn = sqlite3.connect(args.db)
            cursor = conn.cursor()
            
            # Create schema
            create_database_schema(cursor)
            
            # Insert data
            insert_scan_data_to_db(cursor, results)
            
            conn.commit()
            conn.close()
            
            print(f"Database results written to {args.db}", file=sys.stderr)
            
            # Create schema documentation
            schema_file = args.schema
            if not schema_file:
                db_base = os.path.splitext(args.db)[0]
                schema_file = f"{db_base}_schema.json"
            
            create_database_schema_json(schema_file)
            print(f"Database schema documentation written to {schema_file}", file=sys.stderr)
            
        except Exception as e:
            print(f"Error writing to database {args.db}: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Cleanup checkpoint files on successful completion
    if checkpoint_manager:
        checkpoint_manager.cleanup()
        print("Scan completed successfully!", file=sys.stderr)


if __name__ == '__main__':
    main()
