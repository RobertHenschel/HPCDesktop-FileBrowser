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

from pathlib import Path
from datetime import datetime



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
        

        
        return metadata
        
    except (OSError, IOError) as e:
        return {
            'path': filepath,
            'basename': os.path.basename(filepath),
            'error': f"Could not get standard metadata: {str(e)}"
        }


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


def get_directory_metadata(dirpath):
    """Gather comprehensive directory metadata."""
    try:
        dir_stat = os.stat(dirpath)
        
        # Get user and group names
        try:
            username = pwd.getpwuid(dir_stat.st_uid).pw_name
        except KeyError:
            username = str(dir_stat.st_uid)
        
        try:
            groupname = grp.getgrgid(dir_stat.st_gid).gr_name
        except KeyError:
            groupname = str(dir_stat.st_gid)
        
        # Count files and calculate total size
        file_count = 0
        total_size = 0
        direct_files = []
        
        try:
            for item in os.listdir(dirpath):
                item_path = os.path.join(dirpath, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    file_count += 1
                    direct_files.append(item_path)
                    try:
                        file_stat = os.stat(item_path)
                        total_size += file_stat.st_size
                    except (OSError, IOError):
                        pass  # Skip files we can't stat
        except OSError:
            pass  # Handle permission errors
        
        metadata = {
            'path': dirpath,
            'basename': os.path.basename(dirpath),
            'file_count': file_count,
            'total_size_bytes': total_size,
            'total_size_human': format_bytes(total_size),
            'direct_files': direct_files,
            'permissions': {
                'octal': oct(dir_stat.st_mode)[-3:],
                'symbolic': stat.filemode(dir_stat.st_mode),
                'user_readable': bool(dir_stat.st_mode & stat.S_IRUSR),
                'user_writable': bool(dir_stat.st_mode & stat.S_IWUSR),
                'user_executable': bool(dir_stat.st_mode & stat.S_IXUSR),
                'group_readable': bool(dir_stat.st_mode & stat.S_IRGRP),
                'group_writable': bool(dir_stat.st_mode & stat.S_IWGRP),
                'group_executable': bool(dir_stat.st_mode & stat.S_IXGRP),
                'other_readable': bool(dir_stat.st_mode & stat.S_IROTH),
                'other_writable': bool(dir_stat.st_mode & stat.S_IWOTH),
                'other_executable': bool(dir_stat.st_mode & stat.S_IXOTH),
                'setuid': bool(dir_stat.st_mode & stat.S_ISUID),
                'setgid': bool(dir_stat.st_mode & stat.S_ISGID),
                'sticky': bool(dir_stat.st_mode & stat.S_ISVTX)
            },
            'ownership': {
                'uid': dir_stat.st_uid,
                'gid': dir_stat.st_gid,
                'username': username,
                'groupname': groupname
            },
            'timestamps': {
                'access_time': dir_stat.st_atime,
                'modify_time': dir_stat.st_mtime,
                'change_time': dir_stat.st_ctime,
                'access_time_iso': datetime.fromtimestamp(dir_stat.st_atime).isoformat(),
                'modify_time_iso': datetime.fromtimestamp(dir_stat.st_mtime).isoformat(),
                'change_time_iso': datetime.fromtimestamp(dir_stat.st_ctime).isoformat()
            },
            'inode': {
                'number': dir_stat.st_ino,
                'device': dir_stat.st_dev,
                'links': dir_stat.st_nlink
            }
        }
        
        return metadata
        
    except (OSError, IOError) as e:
        return {
            'path': dirpath,
            'basename': os.path.basename(dirpath),
            'error': f"Could not get directory metadata: {str(e)}"
        }


def collect_directory_tree(directory_path, recursive=False, max_depth=None):
    """Collect all directories that will be scanned."""
    directories = set()
    
    # Always include the root directory
    root_path = os.path.abspath(directory_path)
    directories.add(root_path)
    
    if recursive:
        try:
            for root, dirs, files in os.walk(directory_path, followlinks=True):
                # Calculate current depth relative to the starting directory
                if max_depth is not None:
                    current_depth = root.replace(root_path, '').count(os.sep)
                    if current_depth >= max_depth:
                        # Clear dirs to prevent os.walk from going deeper
                        dirs[:] = []
                        continue
                
                directories.add(os.path.abspath(root))
        except OSError:
            pass  # Handle permission errors
    
    return sorted(directories)


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


def create_database_schema(cursor, enable_lustre=False):
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
            total_directories INTEGER,
            recursive BOOLEAN,
            lustre_enabled BOOLEAN
        )
    ''')
    
    # Directories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directories (
            id INTEGER PRIMARY KEY,
            scan_id INTEGER,
            path TEXT NOT NULL,
            basename TEXT,
            parent_directory_id INTEGER,
            file_count INTEGER,
            total_size_bytes INTEGER,
            total_size_human TEXT,
            error_message TEXT,
            FOREIGN KEY (scan_id) REFERENCES scan_info (id),
            FOREIGN KEY (parent_directory_id) REFERENCES directories (id)
        )
    ''')
    
    # Directory permissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directory_permissions (
            id INTEGER PRIMARY KEY,
            directory_id INTEGER,
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
            FOREIGN KEY (directory_id) REFERENCES directories (id)
        )
    ''')
    
    # Directory ownership table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directory_ownership (
            id INTEGER PRIMARY KEY,
            directory_id INTEGER,
            uid INTEGER,
            gid INTEGER,
            username TEXT,
            groupname TEXT,
            FOREIGN KEY (directory_id) REFERENCES directories (id)
        )
    ''')
    
    # Directory timestamps table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directory_timestamps (
            id INTEGER PRIMARY KEY,
            directory_id INTEGER,
            access_time REAL,
            modify_time REAL,
            change_time REAL,
            access_time_iso TEXT,
            modify_time_iso TEXT,
            change_time_iso TEXT,
            FOREIGN KEY (directory_id) REFERENCES directories (id)
        )
    ''')
    
    # Directory inodes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directory_inodes (
            id INTEGER PRIMARY KEY,
            directory_id INTEGER,
            inode_number INTEGER,
            device INTEGER,
            links INTEGER,
            FOREIGN KEY (directory_id) REFERENCES directories (id)
        )
    ''')
    
    # Directory extended attributes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directory_extended_attributes (
            id INTEGER PRIMARY KEY,
            directory_id INTEGER,
            all_attributes TEXT,
            selinux TEXT,
            FOREIGN KEY (directory_id) REFERENCES directories (id)
        )
    ''')
    
    # Directory ACL info table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directory_acl_info (
            id INTEGER PRIMARY KEY,
            directory_id INTEGER,
            posix_acl TEXT,
            FOREIGN KEY (directory_id) REFERENCES directories (id)
        )
    ''')
    
    # Directory-file relationship table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directory_files (
            id INTEGER PRIMARY KEY,
            directory_id INTEGER,
            file_id INTEGER,
            FOREIGN KEY (directory_id) REFERENCES directories (id),
            FOREIGN KEY (file_id) REFERENCES files (id)
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
            directory_id INTEGER,
            FOREIGN KEY (scan_id) REFERENCES scan_info (id),
            FOREIGN KEY (directory_id) REFERENCES directories (id)
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
    

    
    # Lustre metadata table (only created if Lustre is enabled)
    if enable_lustre:
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


def insert_scan_data_to_db(cursor, results, enable_lustre=False):
    """Insert scan results into SQLite database."""
    
    # Insert scan info
    scan_info = results['scan_info']
    cursor.execute('''
        INSERT INTO scan_info (directory, scan_time, scan_completed, hostname, lustre_version, total_files, total_directories, recursive, lustre_enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        scan_info.get('directory'),
        scan_info.get('scan_time'),
        scan_info.get('scan_completed'),
        scan_info.get('hostname'),
        scan_info.get('lustre_version'),
        scan_info.get('total_files'),
        scan_info.get('total_directories'),
        scan_info.get('recursive'),
        scan_info.get('lustre_enabled')
    ))
    
    scan_id = cursor.lastrowid
    
    # Insert directory data first
    directory_id_map = {}  # Map directory path to database ID
    for dir_data in results['directories']:
        dir_meta = dir_data.get('standard_metadata', {})
        
        # Skip directories without a valid path
        dir_path = dir_meta.get('path')
        if not dir_path:
            print(f"Warning: Skipping directory with no path in metadata", file=sys.stderr)
            continue
        
        # Find parent directory ID
        parent_dir_id = None
        parent_path = os.path.dirname(dir_path)
        if parent_path != dir_path and parent_path in directory_id_map:
            parent_dir_id = directory_id_map[parent_path]
        
        # Insert main directory record
        cursor.execute('''
            INSERT INTO directories (scan_id, path, basename, parent_directory_id, file_count, total_size_bytes, total_size_human, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan_id,
            dir_meta.get('path'),
            dir_meta.get('basename'),
            parent_dir_id,
            dir_meta.get('file_count'),
            dir_meta.get('total_size_bytes'),
            dir_meta.get('total_size_human'),
            dir_meta.get('error')
        ))
        
        directory_id = cursor.lastrowid
        directory_id_map[dir_path] = directory_id
        
        # Insert directory permissions
        perms = dir_meta.get('permissions', {})
        if perms:
            cursor.execute('''
                INSERT INTO directory_permissions (directory_id, octal, symbolic, user_readable, user_writable, user_executable,
                                                 group_readable, group_writable, group_executable,
                                                 other_readable, other_writable, other_executable,
                                                 setuid, setgid, sticky)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                directory_id, perms.get('octal'), perms.get('symbolic'),
                perms.get('user_readable'), perms.get('user_writable'), perms.get('user_executable'),
                perms.get('group_readable'), perms.get('group_writable'), perms.get('group_executable'),
                perms.get('other_readable'), perms.get('other_writable'), perms.get('other_executable'),
                perms.get('setuid'), perms.get('setgid'), perms.get('sticky')
            ))
        
        # Insert directory ownership
        ownership = dir_meta.get('ownership', {})
        if ownership:
            cursor.execute('''
                INSERT INTO directory_ownership (directory_id, uid, gid, username, groupname)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                directory_id, ownership.get('uid'), ownership.get('gid'),
                ownership.get('username'), ownership.get('groupname')
            ))
        
        # Insert directory timestamps
        timestamps = dir_meta.get('timestamps', {})
        if timestamps:
            cursor.execute('''
                INSERT INTO directory_timestamps (directory_id, access_time, modify_time, change_time,
                                                access_time_iso, modify_time_iso, change_time_iso)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                directory_id, timestamps.get('access_time'), timestamps.get('modify_time'), timestamps.get('change_time'),
                timestamps.get('access_time_iso'), timestamps.get('modify_time_iso'), timestamps.get('change_time_iso')
            ))
        
        # Insert directory inode info
        inode = dir_meta.get('inode', {})
        if inode:
            cursor.execute('''
                INSERT INTO directory_inodes (directory_id, inode_number, device, links)
                VALUES (?, ?, ?, ?)
            ''', (
                directory_id, inode.get('number'), inode.get('device'), inode.get('links')
            ))
        
        # Insert directory extended attributes
        xattr = dir_data.get('extended_attributes', {})
        if xattr:
            cursor.execute('''
                INSERT INTO directory_extended_attributes (directory_id, all_attributes, selinux)
                VALUES (?, ?, ?)
            ''', (
                directory_id, xattr.get('all_attributes'), xattr.get('selinux')
            ))
        
        # Insert directory ACL info
        acl = dir_data.get('acl_info', {})
        if acl:
            cursor.execute('''
                INSERT INTO directory_acl_info (directory_id, posix_acl)
                VALUES (?, ?)
            ''', (
                directory_id, acl.get('posix_acl')
            ))
    
    # Insert file data
    for file_data in results['files']:
        std_meta = file_data.get('standard_metadata', {})
        
        # Skip files without a valid path
        file_path = std_meta.get('path')
        if not file_path:
            print(f"Warning: Skipping file with no path in metadata", file=sys.stderr)
            continue
        
        # Find directory ID for this file
        file_directory_id = None
        file_dir_path = os.path.dirname(file_path)
        file_directory_id = directory_id_map.get(file_dir_path)
        
        # Insert main file record
        cursor.execute('''
            INSERT INTO files (scan_id, scan_order, path, basename, size_bytes, size_human, file_type, symlink_target, error_message, directory_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan_id,
            file_data.get('scan_order'),
            std_meta.get('path'),
            std_meta.get('basename'),
            std_meta.get('size_bytes'),
            std_meta.get('size_human'),
            std_meta.get('type'),
            std_meta.get('symlink_target'),
            std_meta.get('error'),
            file_directory_id
        ))
        
        file_id = cursor.lastrowid
        
        # Create directory-file relationship
        if file_directory_id:
            cursor.execute('''
                INSERT INTO directory_files (directory_id, file_id)
                VALUES (?, ?)
            ''', (file_directory_id, file_id))
        
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
        

        
        # Insert Lustre metadata (only if Lustre is enabled)
        if enable_lustre:
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


def create_database_schema_json(schema_file, enable_lustre=False):
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
                        "total_directories": {"type": "INTEGER", "description": "Total number of directories scanned"},
                        "recursive": {"type": "BOOLEAN", "description": "Whether the scan was performed recursively"},
                        "lustre_enabled": {"type": "BOOLEAN", "description": "Whether Lustre metadata collection was enabled"}
                    }
                },
                "directories": {
                    "description": "Directory information and metadata",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True, "description": "Unique directory record identifier"},
                        "scan_id": {"type": "INTEGER", "foreign_key": "scan_info.id", "description": "Reference to scan"},
                        "path": {"type": "TEXT", "description": "Full path to the directory"},
                        "basename": {"type": "TEXT", "description": "Directory basename"},
                        "parent_directory_id": {"type": "INTEGER", "foreign_key": "directories.id", "description": "Reference to parent directory"},
                        "file_count": {"type": "INTEGER", "description": "Number of direct files in directory"},
                        "total_size_bytes": {"type": "INTEGER", "description": "Total size of all files in directory in bytes"},
                        "total_size_human": {"type": "TEXT", "description": "Human-readable total size"},
                        "error_message": {"type": "TEXT", "description": "Error message if metadata collection failed"}
                    }
                },
                "directory_permissions": {
                    "description": "Directory permission information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "directory_id": {"type": "INTEGER", "foreign_key": "directories.id"},
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
                "directory_ownership": {
                    "description": "Directory ownership information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "directory_id": {"type": "INTEGER", "foreign_key": "directories.id"},
                        "uid": {"type": "INTEGER", "description": "User ID"},
                        "gid": {"type": "INTEGER", "description": "Group ID"},
                        "username": {"type": "TEXT", "description": "Username"},
                        "groupname": {"type": "TEXT", "description": "Group name"}
                    }
                },
                "directory_timestamps": {
                    "description": "Directory timestamp information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "directory_id": {"type": "INTEGER", "foreign_key": "directories.id"},
                        "access_time": {"type": "REAL", "description": "Access time (Unix timestamp)"},
                        "modify_time": {"type": "REAL", "description": "Modify time (Unix timestamp)"},
                        "change_time": {"type": "REAL", "description": "Change time (Unix timestamp)"},
                        "access_time_iso": {"type": "TEXT", "description": "Access time (ISO format)"},
                        "modify_time_iso": {"type": "TEXT", "description": "Modify time (ISO format)"},
                        "change_time_iso": {"type": "TEXT", "description": "Change time (ISO format)"}
                    }
                },
                "directory_inodes": {
                    "description": "Directory inode information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "directory_id": {"type": "INTEGER", "foreign_key": "directories.id"},
                        "inode_number": {"type": "INTEGER", "description": "Inode number"},
                        "device": {"type": "INTEGER", "description": "Device ID"},
                        "links": {"type": "INTEGER", "description": "Number of hard links"}
                    }
                },
                "directory_extended_attributes": {
                    "description": "Directory extended attributes",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "directory_id": {"type": "INTEGER", "foreign_key": "directories.id"},
                        "all_attributes": {"type": "TEXT", "description": "All extended attributes"},
                        "selinux": {"type": "TEXT", "description": "SELinux security context"}
                    }
                },
                "directory_acl_info": {
                    "description": "Directory Access Control List information",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "directory_id": {"type": "INTEGER", "foreign_key": "directories.id"},
                        "posix_acl": {"type": "TEXT", "description": "POSIX ACL information"}
                    }
                },
                "directory_files": {
                    "description": "Directory-file relationship mapping",
                    "columns": {
                        "id": {"type": "INTEGER", "primary_key": True},
                        "directory_id": {"type": "INTEGER", "foreign_key": "directories.id", "description": "Reference to directory"},
                        "file_id": {"type": "INTEGER", "foreign_key": "files.id", "description": "Reference to file"}
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
                        "error_message": {"type": "TEXT", "description": "Error message if metadata collection failed"},
                        "directory_id": {"type": "INTEGER", "foreign_key": "directories.id", "description": "Reference to containing directory"}
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
                "get_all_directories_from_scan": "SELECT * FROM directories WHERE scan_id = 1;",
                "get_large_files": "SELECT path, size_bytes, size_human FROM files WHERE size_bytes > 1000000 ORDER BY size_bytes DESC;",
                "get_executable_files": "SELECT f.path FROM files f JOIN file_permissions p ON f.id = p.file_id WHERE p.user_executable = 1;",
                "get_recent_files": "SELECT f.path, t.modify_time_iso FROM files f JOIN file_timestamps t ON f.id = t.file_id ORDER BY t.modify_time DESC LIMIT 10;",
                "get_directory_sizes": "SELECT path, file_count, total_size_bytes, total_size_human FROM directories ORDER BY total_size_bytes DESC;",
                "get_files_in_directory": "SELECT f.path, f.size_human FROM files f JOIN directories d ON f.directory_id = d.id WHERE d.path = '/specific/directory/path';",
                "get_directory_tree": "SELECT d1.path as parent, d2.path as child FROM directories d1 LEFT JOIN directories d2 ON d1.id = d2.parent_directory_id ORDER BY d1.path;",
                "get_largest_directories": "SELECT d.path, d.file_count, d.total_size_human FROM directories d ORDER BY d.total_size_bytes DESC LIMIT 10;",
                "get_directory_with_most_files": "SELECT path, file_count, total_size_human FROM directories ORDER BY file_count DESC LIMIT 10;",
                "get_directory_permissions": "SELECT d.path, dp.symbolic, do.username, do.groupname FROM directories d JOIN directory_permissions dp ON d.id = dp.directory_id JOIN directory_ownership do ON d.id = do.directory_id;",
                "get_writable_directories": "SELECT d.path FROM directories d JOIN directory_permissions dp ON d.id = dp.directory_id WHERE dp.user_writable = 1 OR dp.group_writable = 1 OR dp.other_writable = 1;",
                "get_files_and_directories": "SELECT f.path, f.size_human, d.path as directory FROM files f JOIN directories d ON f.directory_id = d.id ORDER BY d.path, f.path;"
            }
        }
    }
    
    # Add Lustre-specific table and examples only if Lustre is enabled
    if enable_lustre:
        schema["database_schema"]["tables"]["lustre_metadata"] = {
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
        }
        # Add Lustre-specific usage examples
        schema["database_schema"]["usage_examples"]["get_files_with_lustre_info"] = "SELECT f.path, l.stripe_count, l.stripe_size FROM files f JOIN lustre_metadata l ON f.id = l.file_id;"
        schema["database_schema"]["usage_examples"]["get_lustre_files_by_directory"] = "SELECT d.path as directory, f.path as file, l.stripe_count FROM directories d JOIN files f ON d.id = f.directory_id JOIN lustre_metadata l ON f.id = l.file_id ORDER BY d.path;"
    
    with open(schema_file, 'w') as f:
        json.dump(schema, f, indent=2)


def scan_directory(directory_path, recursive=False, enable_lustre=False, max_depth=None):
    """Scan directory and gather metadata for all files."""
    if not os.path.isdir(directory_path):
        print(f"Error: '{directory_path}' is not a directory", file=sys.stderr)
        return None
    
    # Initialize results
    scan_info = {
        'directory': os.path.abspath(directory_path),
        'scan_time': datetime.now().isoformat(),
        'hostname': run_command('hostname'),
        'recursive': recursive,
        'lustre_enabled': enable_lustre,
    }
    if enable_lustre:
        scan_info['lustre_version'] = run_command('lfs --version')
    
    results = {
        'scan_info': scan_info,
        'directories': [],
        'files': []
    }
    
    try:
        # Get list of files in directory (and subdirectories if recursive)
        entries = []
        if recursive:
            depth_msg = f" (max depth: {max_depth})" if max_depth is not None else ""
            print(f"Recursively scanning {directory_path}{depth_msg}...", file=sys.stderr)
            root_path = os.path.abspath(directory_path)
            for root, dirs, files in os.walk(directory_path, followlinks=True):
                # Calculate current depth relative to the starting directory
                if max_depth is not None:
                    current_depth = root.replace(root_path, '').count(os.sep)
                    if current_depth >= max_depth:
                        # Clear dirs to prevent os.walk from going deeper
                        dirs[:] = []
                        continue
                
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
        
        # Collect directory information
        print(f"Collecting directory information...", file=sys.stderr)
        directories = collect_directory_tree(directory_path, recursive, max_depth)
        
        for dir_path in directories:
            print(f"Processing directory: {dir_path}", file=sys.stderr)
            dir_metadata = get_directory_metadata(dir_path)
            
            # Add directory metadata
            directory_data = {
                'standard_metadata': dir_metadata,
                'extended_attributes': get_extended_attributes(dir_path),
                'acl_info': get_acl_info(dir_path)
            }
            
            results['directories'].append(directory_data)
        
        total_files = len(entries)
        scan_scope = "recursively" if recursive else ""
        print(f"Found {len(entries)} files to scan {scan_scope} in {directory_path}", file=sys.stderr)
        
        for i, filepath in enumerate(entries, 1):
            # Print progress every 100 files or at the end
            if i % 100 == 0 or i == len(entries):
                print(f"Scanning {i}/{total_files}: {filepath}", file=sys.stderr)
            
            file_metadata = {
                'scan_order': i,
                'standard_metadata': get_standard_metadata(filepath),
                'extended_attributes': get_extended_attributes(filepath),
                'acl_info': get_acl_info(filepath)
            }
            
            # Only gather Lustre metadata if enabled
            if enable_lustre:
                file_metadata['lustre_metadata'] = get_lustre_metadata(filepath)
            
            results['files'].append(file_metadata)
        
        # Update final scan info
        results['scan_info']['total_files'] = total_files
        results['scan_info']['total_directories'] = len(results['directories'])
        results['scan_info']['scan_completed'] = datetime.now().isoformat()
        
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
  %(prog)s /lustre/project/data --lustre --output results.json --db results.db
  %(prog)s /path --recursive --output results.json     # Scan recursively
  %(prog)s /path --recursive --max-depth 4 --output results.json  # Scan 4 levels deep
  %(prog)s /path --lustre --recursive --output lustre.json  # Lustre + recursive
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

    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Recursively scan subdirectories')
    parser.add_argument('--max-depth', type=int, default=None,
                       help='Maximum depth for recursive scanning (default: unlimited, e.g., --max-depth 4)')
    parser.add_argument('--lustre', action='store_true',
                       help='Enable Lustre-specific metadata collection (requires lfs tools)')
    
    args = parser.parse_args()
    

    
    # Validate directory
    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    # Scan directory
    try:
        results = scan_directory(args.directory, args.recursive, args.lustre, args.max_depth)
        if results is None:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nScan interrupted.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during scan: {e}", file=sys.stderr)
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
            create_database_schema(cursor, args.lustre)
            
            # Insert data
            insert_scan_data_to_db(cursor, results, args.lustre)
            
            conn.commit()
            conn.close()
            
            print(f"Database results written to {args.db}", file=sys.stderr)
            
            # Create schema documentation
            schema_file = args.schema
            if not schema_file:
                db_base = os.path.splitext(args.db)[0]
                schema_file = f"{db_base}_schema.json"
            
            create_database_schema_json(schema_file, args.lustre)
            print(f"Database schema documentation written to {schema_file}", file=sys.stderr)
            
        except Exception as e:
            print(f"Error writing to database {args.db}: {e}", file=sys.stderr)
            sys.exit(1)
    
    print("Scan completed successfully!", file=sys.stderr)


if __name__ == '__main__':
    main()
