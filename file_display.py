import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, 
                             QTableWidget, QListWidget, QStackedWidget, 
                             QListWidgetItem, QGridLayout, QScrollArea, 
                             QHBoxLayout, QPushButton)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer


class FileDisplay(QWidget):
    # Signals for future functionality
    file_selected = pyqtSignal(str)  # file path
    directory_changed = pyqtSignal(str)  # directory path
    
    def __init__(self):
        super().__init__()
        self.current_path = ""
        self.current_filesystem_name = ""
        self.folder_icon = None
        self.file_icon = None
        self.load_icons()
        self.setup_ui()
    
    def load_icons(self):
        """Load SVG icons for files and folders"""
        try:
            # Load folder icon
            folder_renderer = QSvgRenderer("resources/folder.svg")
            folder_pixmap = QPixmap(64, 64)
            folder_pixmap.fill(Qt.transparent)
            painter = QPainter(folder_pixmap)
            folder_renderer.render(painter)
            painter.end()
            self.folder_icon = QIcon(folder_pixmap)
            
            # Load file icon
            file_renderer = QSvgRenderer("resources/file.svg")
            file_pixmap = QPixmap(64, 64)
            file_pixmap.fill(Qt.transparent)
            painter = QPainter(file_pixmap)
            file_renderer.render(painter)
            painter.end()
            self.file_icon = QIcon(file_pixmap)
            
        except Exception as e:
            print(f"Warning: Could not load icons: {e}")
            # Fallback to default icons if SVG loading fails
            self.folder_icon = self.style().standardIcon(self.style().SP_DirIcon)
            self.file_icon = self.style().standardIcon(self.style().SP_FileIcon)
    
    def setup_ui(self):
        """Setup the file display UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Breadcrumb navigation - match sidebar title area height
        self.breadcrumb_frame = QFrame()
        self.breadcrumb_frame.setMinimumHeight(35)  # Match sidebar title + separator height
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_frame)
        self.breadcrumb_layout.setContentsMargins(5, 5, 5, 5)
        self.breadcrumb_layout.setSpacing(0)
        
        # Title label (similar to sidebar)
        self.breadcrumb_title = QLabel("Path")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        self.breadcrumb_title.setFont(title_font)
        self.breadcrumb_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.breadcrumb_layout.addWidget(self.breadcrumb_title)
        
        # Separator between title and breadcrumb
        separator_label = QLabel(":")
        separator_label.setStyleSheet("margin: 0 5px;")
        self.breadcrumb_layout.addWidget(separator_label)
        
        # Container for breadcrumb buttons
        self.breadcrumb_container = QWidget()
        self.breadcrumb_container_layout = QHBoxLayout(self.breadcrumb_container)
        self.breadcrumb_container_layout.setContentsMargins(0, 0, 0, 0)
        self.breadcrumb_container_layout.setSpacing(0)
        self.breadcrumb_layout.addWidget(self.breadcrumb_container)
        
        # Add stretch to push breadcrumb to the left
        self.breadcrumb_layout.addStretch()
        
        # Default message
        self.default_breadcrumb = QLabel("Select a filesystem from the sidebar")
        self.default_breadcrumb.setStyleSheet("color: #666666; font-style: italic;")
        self.breadcrumb_container_layout.addWidget(self.default_breadcrumb)
        
        layout.addWidget(self.breadcrumb_frame)
        
        # Main content area
        self.content_widget = QStackedWidget()
        
        # Welcome page
        welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(welcome_widget)
        welcome_layout.setAlignment(Qt.AlignCenter)
        
        welcome_title = QLabel("HPC Desktop File Browser")
        welcome_font = QFont()
        welcome_font.setBold(True)
        welcome_font.setPointSize(16)
        welcome_title.setFont(welcome_font)
        welcome_title.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(welcome_title)
        
        welcome_text = QLabel("Select a filesystem from the sidebar to start browsing files and directories.")
        welcome_text.setAlignment(Qt.AlignCenter)
        welcome_text.setWordWrap(True)
        welcome_text.setStyleSheet("color: #888888; margin: 20px;")
        welcome_layout.addWidget(welcome_text)
        
        self.content_widget.addWidget(welcome_widget)
        
        # File listing widget (grid view)
        self.file_list_widget = QListWidget()
        self.file_list_widget.setViewMode(QListWidget.IconMode)
        self.file_list_widget.setResizeMode(QListWidget.Adjust)
        self.file_list_widget.setGridSize(QSize(120, 100))
        self.file_list_widget.setIconSize(QSize(64, 64))
        self.file_list_widget.setUniformItemSizes(True)
        self.file_list_widget.setWordWrap(True)
        self.file_list_widget.setSpacing(10)
        self.file_list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.content_widget.addWidget(self.file_list_widget)
        
        # Table view widget (for future detailed view)
        self.file_table_widget = QTableWidget()
        self.file_table_widget.setAlternatingRowColors(True)
        self.content_widget.addWidget(self.file_table_widget)
        
        # Set default to welcome page
        self.content_widget.setCurrentIndex(0)
        
        layout.addWidget(self.content_widget)
    
    def set_filesystem(self, name, path):
        """Set the current filesystem being displayed"""
        self.current_filesystem_name = name
        
        # Expand user path (~ to home directory)
        expanded_path = os.path.expanduser(path)
        
        self.current_path = expanded_path
        
        # Update breadcrumb navigation
        self.update_breadcrumb(expanded_path)
        
        # Load and display directory contents
        self.load_directory_contents(expanded_path)
    
    def load_directory_contents(self, path):
        """Load and display the contents of a directory"""
        try:
            # Switch to file list view
            self.content_widget.setCurrentIndex(1)
            
            # Clear existing content
            self.file_list_widget.clear()
            
            if not os.path.exists(path):
                self.show_error(f"Path does not exist: {path}")
                return
                
            if not os.path.isdir(path):
                self.show_error(f"Path is not a directory: {path}")
                return
            
            if not os.access(path, os.R_OK):
                self.show_error(f"Permission denied: {path}")
                return
            
            # Get directory contents
            entries = []
            try:
                for entry in os.listdir(path):
                    entry_path = os.path.join(path, entry)
                    is_dir = os.path.isdir(entry_path)
                    entries.append((entry, is_dir, entry_path))
            except PermissionError:
                self.show_error(f"Permission denied reading directory: {path}")
                return
            
            # Sort entries: directories first, then files, both alphabetically
            entries.sort(key=lambda x: (not x[1], x[0].lower()))
            
            # Add entries to the list
            for entry_name, is_dir, entry_path in entries:
                self.add_file_item(entry_name, is_dir, entry_path)
                
        except Exception as e:
            self.show_error(f"Error loading directory: {str(e)}")
    
    def add_file_item(self, name, is_dir, full_path):
        """Add a file or directory item to the list"""
        # Truncate long filenames
        display_name = self.truncate_filename(name, 15)
        
        # Create list item
        item = QListWidgetItem()
        item.setText(display_name)
        item.setData(Qt.UserRole, {
            'name': name,
            'path': full_path,
            'is_dir': is_dir
        })
        
        # Set icon
        if is_dir:
            item.setIcon(self.folder_icon)
        else:
            item.setIcon(self.file_icon)
        
        # Set tooltip with full name and path
        item.setToolTip(f"{name}\n{full_path}")
        
        # Add to list
        self.file_list_widget.addItem(item)
    
    def truncate_filename(self, filename, max_length):
        """Truncate filename in the middle if it's too long"""
        if len(filename) <= max_length:
            return filename
        
        # Calculate how many characters to keep on each side
        side_length = (max_length - 3) // 2  # 3 for "..."
        
        if side_length <= 0:
            return "..."
        
        return f"{filename[:side_length]}...{filename[-side_length:]}"
    
    def show_error(self, message):
        """Show error message in the file list"""
        self.content_widget.setCurrentIndex(1)
        self.file_list_widget.clear()
        
        error_item = QListWidgetItem()
        error_item.setText("Error")
        error_item.setIcon(self.style().standardIcon(self.style().SP_MessageBoxCritical))
        error_item.setToolTip(message)
        error_item.setFlags(error_item.flags() & ~Qt.ItemIsSelectable)
        
        self.file_list_widget.addItem(error_item)
    
    def on_item_double_clicked(self, item):
        """Handle double-click on file/folder items"""
        data = item.data(Qt.UserRole)
        if not data:
            return
            
        if data['is_dir']:
            # Navigate into directory
            new_path = data['path']
            self.current_path = new_path
            
            # Update breadcrumb navigation
            self.update_breadcrumb(new_path)
            
            self.load_directory_contents(new_path)
            
            # Emit signal for other components
            self.directory_changed.emit(new_path)
        else:
            # File selected
            file_path = data['path']
            self.file_selected.emit(file_path)
            print(f"File selected: {file_path}")
    
    def clear_display(self):
        """Clear the file display and return to welcome screen"""
        self.current_path = ""
        self.clear_breadcrumb()
        self.content_widget.setCurrentIndex(0)
    
    def refresh(self):
        """Refresh the current directory contents"""
        if self.current_path:
            print(f"Refreshing contents of: {self.current_path}")
            self.load_directory_contents(self.current_path)
        
    def get_current_path(self):
        """Get the current path being displayed"""
        return self.current_path
    
    def update_breadcrumb(self, path):
        """Update the breadcrumb navigation with the current path"""
        # Clear existing breadcrumb buttons
        self.clear_breadcrumb_buttons()
        
        # Hide default message  
        self.default_breadcrumb.hide()
        
        # Simple approach: just split the current path and display it
        # Remove any trailing slash except for root
        clean_path = path.rstrip('/') if path != '/' else '/'
        
        # Split the path into segments
        if clean_path == '/':
            segments = ['/']
        else:
            # Split by '/' and filter out empty strings
            parts = [p for p in clean_path.split('/') if p]
            segments = ['/'] + parts
        
        # Create breadcrumb buttons for each segment
        for i, segment in enumerate(segments):
            # Add separator before each segment (except the first)
            if i > 0:
                separator = QLabel("/")
                separator.setStyleSheet("color: #666666; margin: 0 2px;")
                self.breadcrumb_container_layout.addWidget(separator)
            
            # Create the clickable button
            button = QPushButton(segment)
            button.setFlat(True)
            button.setStyleSheet("""
                QPushButton {
                    border: none;
                    padding: 2px 4px;
                    text-align: left;
                    color: #0066cc;
                    background: transparent;
                }
                QPushButton:hover {
                    background-color: #e6f3ff;
                    border-radius: 3px;
                }
                QPushButton:pressed {
                    background-color: #cce6ff;
                }
            """)
            
            # Build the path for this segment
            if i == 0:
                # Root segment
                target_path = "/"
            else:
                # Build path from root to this segment
                target_path = "/" + "/".join(segments[1:i+1])
            
            # Connect the click handler
            button.clicked.connect(lambda checked, tp=target_path: self.navigate_to_breadcrumb_path(tp))
            
            self.breadcrumb_container_layout.addWidget(button)
    
    def clear_breadcrumb(self):
        """Clear breadcrumb and show default message"""
        self.clear_breadcrumb_buttons()
        self.default_breadcrumb.show()
    
    def clear_breadcrumb_buttons(self):
        """Remove all breadcrumb buttons and separators"""
        # Remove all widgets except the default_breadcrumb
        while self.breadcrumb_container_layout.count() > 0:
            child = self.breadcrumb_container_layout.takeAt(0)
            if child.widget() and child.widget() != self.default_breadcrumb:
                child.widget().deleteLater()
        
        # Re-add the default_breadcrumb to ensure it's in the layout
        if self.default_breadcrumb.parent() is None:
            self.breadcrumb_container_layout.addWidget(self.default_breadcrumb)
    
    def navigate_to_breadcrumb_path(self, path):
        """Navigate to a path clicked in the breadcrumb"""
        if os.path.exists(path) and os.path.isdir(path):
            self.current_path = path
            self.update_breadcrumb(path)
            self.load_directory_contents(path)
            
            # Emit signal for other components
            self.directory_changed.emit(path)
        else:
            print(f"Cannot navigate to {path}: path does not exist or is not a directory") 