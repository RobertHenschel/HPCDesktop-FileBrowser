import os
import glob
import re
import json
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer


def on_foldersize_zero_clicked(file_display_widget):
    """Handle folder size visualization - resize folder icons based on scan data file counts"""
    current_path = file_display_widget.get_current_path()
    if not current_path:
        return
    
    # Get the last part of the current path and format it like the scan filename
    path_last_part = current_path.rstrip('/').replace('/', '_').replace('\\', '_').replace(':', '_')
    if not path_last_part:
        return
    
    # Check ./dirscans directory for matching JSON files
    dirscan_dir = "./dirscans"
    if not os.path.exists(dirscan_dir):
        return
    
    # Pattern: YYYYMMDD_HHMMSS_<lastpart>.json
    pattern = f"*_{path_last_part}.json"
    json_files = glob.glob(os.path.join(dirscan_dir, pattern))
    
    if json_files:
        for json_file in json_files:
            filename = os.path.basename(json_file)
            # Verify the pattern matches YYYYMMDD_HHMMSS_<lastpart>.json
            if re.match(r'^\d{8}_\d{6}_.*\.json$', filename):
                try:
                    # Load and parse the JSON file
                    with open(json_file, 'r') as f:
                        scan_data = json.load(f)
                    
                    # Get the analyzed directory from the JSON
                    analyzed_dir = scan_data.get('analyzed_directory', '')
                    paths = scan_data.get('paths', {})
                    
                    # Find direct subdirectories of the analyzed directory
                    direct_subdirs = {}  # folder_name -> file_count
                    for path_key in paths.keys():
                        # Check if this path is a direct child of the analyzed directory
                        if path_key != analyzed_dir and path_key.startswith(analyzed_dir):
                            # Remove the analyzed_dir prefix and check if it's a direct child
                            relative_path = path_key[len(analyzed_dir):].lstrip('/')
                            # If there are no more '/' characters, it's a direct child
                            if '/' not in relative_path and relative_path:
                                folder_name = relative_path
                                file_count = paths[path_key].get('file_count', 0)
                                direct_subdirs[folder_name] = file_count
                    
                    if direct_subdirs:
                        resize_folder_icons_by_file_count(file_display_widget, direct_subdirs)
                        break  # Only process the first matching file
                        
                except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
                    continue  # Try next file if this one fails


def resize_folder_icons_by_file_count(file_display_widget, folder_file_counts):
    """Resize folder icons based on file counts from scan data"""
    if not folder_file_counts:
        return
    
    # Get min and max file counts
    file_counts = list(folder_file_counts.values())
    min_count = min(file_counts)
    max_count = max(file_counts)
    
    # If all folders have the same count, use current zoom level
    if min_count == max_count:
        return
    
    # Map to zoom levels (32 to 128)
    min_size = file_display_widget.zoom_levels[0]  # 32
    max_size = file_display_widget.zoom_levels[-1]  # 128
    
    # Update icons for folders in the current view
    for i in range(file_display_widget.file_list_widget.count()):
        item = file_display_widget.file_list_widget.item(i)
        if item:
            data = item.data(Qt.UserRole)
            if data and data.get('is_dir', False):
                folder_name = data.get('name', '')
                if folder_name in folder_file_counts:
                    file_count = folder_file_counts[folder_name]
                    
                    # Calculate icon size based on file count
                    if max_count > min_count:
                        # Linear interpolation
                        ratio = (file_count - min_count) / (max_count - min_count)
                        icon_size = int(min_size + ratio * (max_size - min_size))
                    else:
                        icon_size = min_size
                    
                    # Create folder icon at the calculated size
                    folder_icon = create_folder_icon_at_size(file_display_widget, icon_size)
                    if folder_icon:
                        item.setIcon(folder_icon)


def create_folder_icon_at_size(file_display_widget, icon_size):
    """Create a folder icon at the specified size"""
    try:
        folder_renderer = QSvgRenderer("resources/folder.svg")
        folder_pixmap = QPixmap(icon_size, icon_size)
        folder_pixmap.fill(Qt.transparent)
        painter = QPainter(folder_pixmap)
        file_display_widget._render_svg_centered(painter, folder_renderer, icon_size)
        painter.end()
        return QIcon(folder_pixmap)
    except Exception:
        return None 