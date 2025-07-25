import os
import glob
import re
import json
import subprocess
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


def on_foldersize_one_clicked(file_display_widget):
    """Handle folder size visualization with fresh scan - build directory scan and resize folder icons"""
    current_path = file_display_widget.get_current_path()
    if not current_path:
        return
    
    # Call the build_directory_json.py script to create a fresh scan
    script_path = "./dirscans/build_directory_json.py"
    if not os.path.exists(script_path):
        print(f"Script not found: {script_path}")
        return
    
    try:
        # Run the script with the current path as argument (blocking UI)
        print(f"Building directory scan for: {current_path}")
        result = subprocess.run([
            "python", script_path, current_path
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        if result.returncode != 0:
            print(f"Script failed with return code {result.returncode}")
            if result.stderr:
                print(f"Error output: {result.stderr}")
            return
        
        print("Directory scan completed successfully")
        
        # Now use the same logic as foldersize zero to resize icons
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
            # Sort by filename to get the most recent one (since we just created it)
            json_files.sort(reverse=True)
            
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
        else:
            print("No matching JSON files found after scan")
            
    except subprocess.TimeoutExpired:
        print("Script timed out after 5 minutes")
    except subprocess.SubprocessError as e:
        print(f"Error running script: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def resize_folder_icons_by_file_count(file_display_widget, folder_file_counts):
    """Resize folder icons based on file counts from scan data"""
    if not folder_file_counts:
        return
    
    # Get min and max file counts
    file_counts = list(folder_file_counts.values())
    min_count = min(file_counts)
    max_count = max(file_counts)
    
    # Determine if we should use variable sizing
    use_variable_sizing = (min_count != max_count)
    
    # Map to zoom levels (32 to 128)
    min_size = file_display_widget.zoom_levels[0]  # 32
    max_size = file_display_widget.zoom_levels[-1]  # 128
    current_zoom_size = file_display_widget.zoom_levels[file_display_widget.current_zoom_index]
    
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
                    if use_variable_sizing:
                        # Linear interpolation when counts vary
                        ratio = (file_count - min_count) / (max_count - min_count)
                        icon_size = int(min_size + ratio * (max_size - min_size))
                    else:
                        # Use current zoom level when all counts are the same
                        icon_size = current_zoom_size
                    
                    # Create folder icon at the calculated size with badge
                    folder_icon = create_folder_icon_at_size(file_display_widget, icon_size, file_count)
                    if folder_icon:
                        item.setIcon(folder_icon)


def create_folder_icon_at_size(file_display_widget, icon_size, file_count=None):
    """Create a folder icon at the specified size with optional file count badge"""
    try:
        folder_renderer = QSvgRenderer("resources/folder.svg")
        folder_pixmap = QPixmap(icon_size, icon_size)
        folder_pixmap.fill(Qt.transparent)
        painter = QPainter(folder_pixmap)
        
        # Render the folder icon
        file_display_widget._render_svg_centered(painter, folder_renderer, icon_size)
        
        # Add badge with file count if provided
        if file_count is not None:
            draw_file_count_badge(painter, icon_size, file_count)
        
        painter.end()
        return QIcon(folder_pixmap)
    except Exception:
        return None


def draw_file_count_badge(painter, icon_size, file_count):
    """Draw a badge with file count on the folder icon"""
    from PyQt5.QtGui import QBrush, QPen, QFont
    from PyQt5.QtCore import QRectF
    
    # Convert file count to string, with abbreviated format for large numbers
    if file_count >= 1000000:
        count_text = f"{file_count // 1000000}M"
    elif file_count >= 1000:
        count_text = f"{file_count // 1000}K"
    else:
        count_text = str(file_count)
    
    # Calculate badge size based on icon size and text length
    badge_size = max(int(icon_size * 0.4), 16)  # At least 16px, up to 40% of icon
    font_size = max(int(badge_size * 0.4), 8)   # Font proportional to badge
    
    # Position badge in top-right corner
    badge_x = icon_size - badge_size - 2
    badge_y = 2
    
    # Set up font
    font = QFont()
    font.setPointSize(font_size)
    font.setBold(True)
    painter.setFont(font)
    
    # Calculate text metrics to center text in badge
    font_metrics = painter.fontMetrics()
    text_width = font_metrics.width(count_text)
    text_height = font_metrics.height()
    
    # Adjust badge size if text is too wide
    if text_width > badge_size - 4:
        badge_size = text_width + 6
        badge_x = icon_size - badge_size - 2
    
    # Draw badge background (red circle)
    painter.setBrush(QBrush(Qt.red))
    painter.setPen(QPen(Qt.white, 1))
    badge_rect = QRectF(badge_x, badge_y, badge_size, badge_size)
    painter.drawEllipse(badge_rect)
    
    # Draw text centered in badge
    text_x = badge_x + (badge_size - text_width) / 2
    text_y = badge_y + (badge_size + text_height) / 2 - font_metrics.descent()
    
    painter.setPen(QPen(Qt.white))
    painter.drawText(int(text_x), int(text_y), count_text) 