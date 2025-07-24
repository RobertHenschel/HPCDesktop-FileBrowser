import os
import stat
import datetime
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QScrollArea
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette

from nsNotebook import NotebookWidget


class DetailsView(QWidget):
    """Details view component that shows information about the current directory or selected file/folder"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = ""
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the details view UI with notebook tabs"""
        # Set pastel blue background for the outer container only
        self.setStyleSheet("""
            DetailsView {
                background-color: #B8D8FF;
                border: 2px solid #7BB3FF;
            }
        """)
        
        # Also set a solid background color as backup
        palette = self.palette()
        palette.setColor(QPalette.Background, palette.color(QPalette.Background).fromRgb(184, 216, 255))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 10, 2, 2)  # Minimal margins
        layout.setSpacing(2)  # Minimal spacing
        
        # Create tabs for different information views
        self.general_tab = self.create_general_tab()
        self.properties_tab = self.create_properties_tab()
        self.details_tab = self.create_details_tab()
        self.metadata_tab = self.create_metadata_tab()
        
        tabs = [
            ("General", self.general_tab),
            ("Properties", self.properties_tab),
            ("Details", self.details_tab),
            ("Metadata", self.metadata_tab)
        ]
        
        # Create notebook widget with custom tabs
        self.notebook = NotebookWidget(tabs=tabs)
        layout.addWidget(self.notebook)
        
        # Set minimum height
        self.setMinimumHeight(60)
        
    def create_general_tab(self):
        """Create the general information tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.general_label = QLabel("No item selected")
        self.general_label.setStyleSheet("color: #333333; font-style: italic; background-color: transparent;")
        self.general_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.general_label.setWordWrap(True)
        layout.addWidget(self.general_label)
        layout.addStretch()
        
        return widget
    
    def create_properties_tab(self):
        """Create the properties tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.properties_label = QLabel("No item selected")
        self.properties_label.setStyleSheet("color: #333333; font-style: italic; background-color: transparent;")
        self.properties_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.properties_label.setWordWrap(True)
        layout.addWidget(self.properties_label)
        layout.addStretch()
        
        return widget
    
    def create_details_tab(self):
        """Create the details tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.details_label = QLabel("No item selected")
        self.details_label.setStyleSheet("color: #333333; font-style: italic; background-color: transparent;")
        self.details_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)
        layout.addStretch()
        
        return widget
    
    def create_metadata_tab(self):
        """Create the metadata tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.metadata_content = QWidget()
        self.metadata_layout = QVBoxLayout(self.metadata_content)
        self.metadata_layout.setContentsMargins(5, 5, 5, 5)
        
        self.metadata_label = QLabel("No item selected")
        self.metadata_label.setStyleSheet("color: #333333; font-style: italic; background-color: transparent;")
        self.metadata_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.metadata_label.setWordWrap(True)
        self.metadata_layout.addWidget(self.metadata_label)
        self.metadata_layout.addStretch()
        
        scroll_area.setWidget(self.metadata_content)
        layout.addWidget(scroll_area)
        
        return widget
        
    def set_current_directory(self, path):
        """Update the details view with information about the current directory"""
        self.current_path = path
        if path and os.path.exists(path):
            self.update_directory_info(path)
        else:
            self.clear_info()
    
    def set_selected_item(self, path, is_directory=False):
        """Update the details view with information about a selected file or folder"""
        self.current_path = path
        if path and os.path.exists(path):
            if is_directory:
                self.update_directory_info(path)
            else:
                self.update_file_info(path)
        else:
            self.clear_info()
    
    def update_directory_info(self, path):
        """Update tabs with directory information"""
        try:
            dir_name = os.path.basename(path) or path
            stat_info = os.stat(path)
            
            # Count items in directory
            try:
                items = os.listdir(path)
                total_items = len(items)
                files_count = sum(1 for item in items if os.path.isfile(os.path.join(path, item)))
                dirs_count = total_items - files_count
            except PermissionError:
                total_items = files_count = dirs_count = "Permission denied"
            
            # General tab
            general_text = f"""<b>Directory:</b> {dir_name}
<br><b>Path:</b> {path}
<br><b>Contents:</b> {total_items} items ({dirs_count} folders, {files_count} files)"""
            self.general_label.setText(general_text)
            self.general_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # Properties tab
            mode = stat_info.st_mode
            permissions = stat.filemode(mode)
            created = datetime.datetime.fromtimestamp(stat_info.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            modified = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            accessed = datetime.datetime.fromtimestamp(stat_info.st_atime).strftime("%Y-%m-%d %H:%M:%S")
            
            properties_text = f"""<b>Permissions:</b> {permissions}
<br><b>Owner UID:</b> {stat_info.st_uid}
<br><b>Group GID:</b> {stat_info.st_gid}
<br><b>Created:</b> {created}
<br><b>Modified:</b> {modified}
<br><b>Accessed:</b> {accessed}"""
            self.properties_label.setText(properties_text)
            self.properties_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # Details tab
            details_text = f"""<b>Full Path:</b> {os.path.abspath(path)}
<br><b>Parent Directory:</b> {os.path.dirname(path)}
<br><b>Type:</b> Directory
<br><b>Inode:</b> {stat_info.st_ino}
<br><b>Device:</b> {stat_info.st_dev}"""
            self.details_label.setText(details_text)
            self.details_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # Metadata tab
            metadata_text = f"""<b>System Information:</b>
<br>• Inode: {stat_info.st_ino}
<br>• Device: {stat_info.st_dev}
<br>• Number of links: {stat_info.st_nlink}
<br>• Block size: {getattr(stat_info, 'st_blksize', 'N/A')}
<br>• Blocks: {getattr(stat_info, 'st_blocks', 'N/A')}"""
            self.metadata_label.setText(metadata_text)
            self.metadata_label.setStyleSheet("color: #333333; background-color: transparent;")
            
        except Exception as e:
            error_text = f"<b>Error reading directory:</b> {str(e)}"
            self.general_label.setText(error_text)
            self.properties_label.setText(error_text)
            self.details_label.setText(error_text)
            self.metadata_label.setText(error_text)
    
    def update_file_info(self, path):
        """Update tabs with file information"""
        try:
            filename = os.path.basename(path)
            stat_info = os.stat(path)
            file_size = stat_info.st_size
            
            # Format file size
            if file_size < 1024:
                size_str = f"{file_size} bytes"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            elif file_size < 1024 * 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{file_size / (1024 * 1024 * 1024):.1f} GB"
            
            # Get file extension
            _, ext = os.path.splitext(filename)
            file_type = ext.upper()[1:] if ext else "File"
            
            # General tab
            general_text = f"""<b>File:</b> {filename}
<br><b>Path:</b> {path}
<br><b>Size:</b> {size_str}
<br><b>Type:</b> {file_type} file"""
            self.general_label.setText(general_text)
            self.general_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # Properties tab
            mode = stat_info.st_mode
            permissions = stat.filemode(mode)
            created = datetime.datetime.fromtimestamp(stat_info.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            modified = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            accessed = datetime.datetime.fromtimestamp(stat_info.st_atime).strftime("%Y-%m-%d %H:%M:%S")
            
            properties_text = f"""<b>Permissions:</b> {permissions}
<br><b>Owner UID:</b> {stat_info.st_uid}
<br><b>Group GID:</b> {stat_info.st_gid}
<br><b>Size:</b> {file_size} bytes ({size_str})
<br><b>Created:</b> {created}
<br><b>Modified:</b> {modified}
<br><b>Accessed:</b> {accessed}"""
            self.properties_label.setText(properties_text)
            self.properties_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # Details tab
            details_text = f"""<b>Full Path:</b> {os.path.abspath(path)}
<br><b>Directory:</b> {os.path.dirname(path)}
<br><b>Filename:</b> {os.path.splitext(filename)[0]}
<br><b>Extension:</b> {ext or 'None'}
<br><b>Type:</b> Regular file
<br><b>Inode:</b> {stat_info.st_ino}
<br><b>Device:</b> {stat_info.st_dev}"""
            self.details_label.setText(details_text)
            self.details_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # Metadata tab
            metadata_text = f"""<b>System Information:</b>
<br>• Inode: {stat_info.st_ino}
<br>• Device: {stat_info.st_dev}
<br>• Number of links: {stat_info.st_nlink}
<br>• Block size: {getattr(stat_info, 'st_blksize', 'N/A')}
<br>• Blocks: {getattr(stat_info, 'st_blocks', 'N/A')}

<br><br><b>File Information:</b>
<br>• Absolute path: {os.path.abspath(path)}
<br>• Real path: {os.path.realpath(path)}
<br>• Is symbolic link: {os.path.islink(path)}"""
            
            # Add MIME type if possible
            try:
                import mimetypes
                mime_type, encoding = mimetypes.guess_type(path)
                if mime_type:
                    metadata_text += f"<br>• MIME type: {mime_type}"
                if encoding:
                    metadata_text += f"<br>• Encoding: {encoding}"
            except:
                pass
                
            self.metadata_label.setText(metadata_text)
            self.metadata_label.setStyleSheet("color: #333333; background-color: transparent;")
            
        except Exception as e:
            error_text = f"<b>Error reading file:</b> {str(e)}"
            self.general_label.setText(error_text)
            self.properties_label.setText(error_text)
            self.details_label.setText(error_text)
            self.metadata_label.setText(error_text)
    
    def clear_info(self):
        """Clear all tab information"""
        clear_text = "No item selected"
        style = "color: #666666; font-style: italic; background-color: transparent;"
        
        self.general_label.setText(clear_text)
        self.general_label.setStyleSheet(style)
        
        self.properties_label.setText(clear_text)
        self.properties_label.setStyleSheet(style)
        
        self.details_label.setText(clear_text)
        self.details_label.setStyleSheet(style)
        
        self.metadata_label.setText(clear_text)
        self.metadata_label.setStyleSheet(style)
    
    def clear(self):
        """Clear the details view"""
        self.current_path = ""
        self.clear_info() 