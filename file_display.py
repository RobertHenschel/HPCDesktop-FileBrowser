import os
import time
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, 
                             QTableWidget, QListWidget, QStackedWidget, 
                             QListWidgetItem, QGridLayout, QScrollArea, 
                             QHBoxLayout, QPushButton, QProgressBar, QToolBar, QAction, QAbstractScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread, QTimer, QPropertyAnimation, QEasingCurve, QRectF
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QTransform
from PyQt5.QtSvg import QSvgRenderer

import foldersize_actions


class DirectoryWorker(QThread):
    """Worker thread for loading directory contents without blocking the UI"""
    # Signals
    contents_loaded = pyqtSignal(list)  # [(name, is_dir, path), ...]
    error_occurred = pyqtSignal(str)
    
    def __init__(self, path):
        super().__init__()
        self.path = path
        self._cancelled = False
    
    def cancel(self):
        """Cancel the current operation"""
        self._cancelled = True
        
    def run(self):
        """Load directory contents in background thread"""
        try:
            if self._cancelled:
                return
                
            if not os.path.exists(self.path):
                if not self._cancelled:
                    self.error_occurred.emit(f"Path does not exist: {self.path}")
                return
                
            if not os.path.isdir(self.path):
                if not self._cancelled:
                    self.error_occurred.emit(f"Path is not a directory: {self.path}")
                return
            
            if not os.access(self.path, os.R_OK):
                if not self._cancelled:
                    self.error_occurred.emit(f"Permission denied: {self.path}")
                return
            
            # Get directory contents
            entries = []
            try:
                for entry in os.listdir(self.path):
                    if self._cancelled:
                        return
                    entry_path = os.path.join(self.path, entry)
                    is_dir = os.path.isdir(entry_path)
                    entries.append((entry, is_dir, entry_path))
            except PermissionError:
                if not self._cancelled:
                    self.error_occurred.emit(f"Permission denied reading directory: {self.path}")
                return
            
            if self._cancelled:
                return
                
            # Sort entries: directories first, then files, both alphabetically
            entries.sort(key=lambda x: (not x[1], x[0].lower()))
            
            if not self._cancelled:
                self.contents_loaded.emit(entries)
                
        except Exception as e:
            if not self._cancelled:
                self.error_occurred.emit(f"Error loading directory: {str(e)}")


class VerticalToolbar(QWidget):
    """Vertical toolbar with zoom controls for the file display"""
    
    # Signals
    zoom_in_requested = pyqtSignal()
    zoom_out_requested = pyqtSignal()
    foldersize_zero_requested = pyqtSignal()
    foldersize_one_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(30)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the vertical toolbar UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 5, 10)
        layout.setSpacing(5)
        
        # Zoom In button (Plus)
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(20, 20)
        self.zoom_in_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #f0f0f0;
                border: 2px outset #d0d0d0;
                border-radius: 4px;
                padding: 0px 0px 4px 0px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                border: 2px inset #d0d0d0;
                background-color: #d0d0d0;
            }
        """)
        self.zoom_in_btn.clicked.connect(self.zoom_in_requested.emit)
        self.zoom_in_btn.setToolTip("Zoom In")
        layout.addWidget(self.zoom_in_btn)
        
        # Zoom Out button (Minus)
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setFixedSize(20, 20)
        self.zoom_out_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #f0f0f0;
                border: 2px outset #d0d0d0;
                border-radius: 4px;
                padding: 0px 0px 3px 0px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                border: 2px inset #d0d0d0;
                background-color: #d0d0d0;
            }
        """)
        self.zoom_out_btn.clicked.connect(self.zoom_out_requested.emit)
        self.zoom_out_btn.setToolTip("Zoom Out")
        layout.addWidget(self.zoom_out_btn)
        
        # Foldersize Zero button (0)
        self.foldersize_zero_btn = QPushButton("0")
        self.foldersize_zero_btn.setFixedSize(20, 20)
        self.foldersize_zero_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #f0f0f0;
                border: 2px outset #d0d0d0;
                border-radius: 4px;
                padding: 0px 0px 3px 0px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                border: 2px inset #d0d0d0;
                background-color: #d0d0d0;
            }
        """)
        self.foldersize_zero_btn.clicked.connect(self.foldersize_zero_requested.emit)
        self.foldersize_zero_btn.setToolTip("Resize folder icons based on file counts in folder")
        layout.addWidget(self.foldersize_zero_btn)
        
        # Foldersize One button (1)
        self.foldersize_one_btn = QPushButton("1")
        self.foldersize_one_btn.setFixedSize(20, 20)
        self.foldersize_one_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #f0f0f0;
                border: 2px outset #d0d0d0;
                border-radius: 4px;
                padding: 0px 0px 3px 0px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                border: 2px inset #d0d0d0;
                background-color: #d0d0d0;
            }
        """)
        self.foldersize_one_btn.clicked.connect(self.foldersize_one_requested.emit)
        self.foldersize_one_btn.setToolTip("Build directory scan and resize folder icons")
        layout.addWidget(self.foldersize_one_btn)
        
        # Add stretch to push buttons to top
        layout.addStretch()
        
        # Style the toolbar background
        self.setStyleSheet("""
            VerticalToolbar {
                background-color: #f8f8f8;
                border-right: 1px solid #cccccc;
            }
        """)


class ClickableListWidget(QListWidget):
    """Custom QListWidget that handles clicks in empty areas"""
    
    # Signal for empty area clicks
    empty_area_clicked = pyqtSignal()
    
    def mousePressEvent(self, event):
        """Override mouse press to detect empty area clicks"""
        # Check if click is on an item
        item = self.itemAt(event.pos())
        
        if item is None:
            # Click was in empty area
            self.clearSelection()  # Clear any selection
            self.empty_area_clicked.emit()  # Emit signal
        
        # Call parent implementation for normal behavior
        super().mousePressEvent(event)


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
        self.extension_icons = {}  # Dictionary to store extension-specific icons
        self.extension_mapping = {}  # Dictionary to map extensions to icon files
        self.worker = None  # Current directory loading worker
        
        # Zoom levels for icon view
        self.zoom_levels = [32, 48, 64, 80, 96, 128]  # Icon sizes
        self.current_zoom_index = 2  # Start at 64px (index 2)
        
        # Build extension mapping and load icons
        self.build_extension_mapping()
        self.load_icons()
        self.setup_ui()
    
    def closeEvent(self, event):
        """Clean up when widget is being destroyed"""
        self._cleanup_worker()
        event.accept()
    
    def __del__(self):
        """Destructor - ensure cleanup"""
        self._cleanup_worker()
    
    def build_extension_mapping(self):
        """Build mapping of file extensions to available icon files"""
        try:
            icon_dir = "resources/files"
            if not os.path.exists(icon_dir):
                print(f"Warning: Extension icons directory not found: {icon_dir}")
                return
            
            # Scan directory for SVG files
            for filename in os.listdir(icon_dir):
                if filename.endswith('.svg') and filename != 'blank.svg':  # Skip blank.svg
                    # Extract extension name (remove .svg)
                    extension = filename[:-4].lower()
                    icon_path = os.path.join(icon_dir, filename)
                    
                    # Map extension to icon path
                    self.extension_mapping[extension] = icon_path
                    
                    # Also handle some common extension variations
                    if extension == 'jpeg':
                        self.extension_mapping['jpg'] = icon_path
                    elif extension == 'mpeg':
                        self.extension_mapping['mpg'] = icon_path
                    elif extension == 'html':
                        self.extension_mapping['htm'] = icon_path
                    elif extension == 'javascript':
                        self.extension_mapping['js'] = icon_path
                    elif extension == 'typescript':
                        self.extension_mapping['ts'] = icon_path
            
            print(f"Loaded {len(self.extension_mapping)} file extension icon mappings")
            
        except Exception as e:
            print(f"Warning: Could not build extension mapping: {e}")
    
    def load_icons(self, icon_size=64):
        """Load SVG icons for files, folders, and all extensions at the specified size"""
        try:
            # Load folder icon
            folder_renderer = QSvgRenderer("resources/folder.svg")
            folder_pixmap = QPixmap(icon_size, icon_size)
            folder_pixmap.fill(Qt.transparent)
            painter = QPainter(folder_pixmap)
            self._render_svg_centered(painter, folder_renderer, icon_size)
            painter.end()
            self.folder_icon = QIcon(folder_pixmap)
            
            # Load default file icon
            file_renderer = QSvgRenderer("resources/file.svg")
            file_pixmap = QPixmap(icon_size, icon_size)
            file_pixmap.fill(Qt.transparent)
            painter = QPainter(file_pixmap)
            self._render_svg_centered(painter, file_renderer, icon_size)
            painter.end()
            self.file_icon = QIcon(file_pixmap)
            
            # Pre-load all extension-specific icons
            self.extension_icons.clear()
            for extension, icon_path in self.extension_mapping.items():
                try:
                    renderer = QSvgRenderer(icon_path)
                    if renderer.isValid():
                        pixmap = QPixmap(icon_size, icon_size)
                        pixmap.fill(Qt.transparent)
                        painter = QPainter(pixmap)
                        self._render_svg_centered(painter, renderer, icon_size)
                        painter.end()
                        self.extension_icons[extension] = QIcon(pixmap)
                except Exception as e:
                    print(f"Warning: Could not load icon for extension '{extension}': {e}")
            
            print(f"Pre-loaded {len(self.extension_icons)} extension-specific icons at size {icon_size}px")
            
        except Exception as e:
            print(f"Warning: Could not load icons: {e}")
            # Fallback to default icons if SVG loading fails
            self.folder_icon = self.style().standardIcon(self.style().SP_DirIcon)
            self.file_icon = self.style().standardIcon(self.style().SP_FileIcon)
    
    def _render_svg_centered(self, painter, renderer, target_size):
        """Render SVG content centered and properly scaled within a square target area"""
        if not renderer.isValid():
            return
        
        # Get the SVG's natural size
        svg_size = renderer.defaultSize()
        if svg_size.width() <= 0 or svg_size.height() <= 0:
            # If SVG doesn't have valid dimensions, render to full target area
            renderer.render(painter, QRectF(0, 0, target_size, target_size))
            return
        
        # Calculate scaling to fit within target size while maintaining aspect ratio
        svg_aspect = svg_size.width() / svg_size.height()
        target_aspect = 1.0  # Square target
        
        if svg_aspect > target_aspect:
            # SVG is wider than target - scale by width
            scaled_width = target_size
            scaled_height = target_size / svg_aspect
        else:
            # SVG is taller than target - scale by height
            scaled_width = target_size * svg_aspect
            scaled_height = target_size
        
        # Center the scaled SVG within the target area
        x_offset = (target_size - scaled_width) / 2
        y_offset = (target_size - scaled_height) / 2
        
        # Render the SVG to the calculated rectangle
        target_rect = QRectF(x_offset, y_offset, scaled_width, scaled_height)
        renderer.render(painter, target_rect)
    
    def get_icon_for_file(self, filename):
        """Get the appropriate icon for a file based on its extension"""
        if not filename:
            return self.file_icon
        
        # Extract file extension
        _, ext = os.path.splitext(filename)
        if not ext:
            return self.file_icon
        
        # Remove the dot and convert to lowercase
        ext = ext[1:].lower()
        
        # Look up extension-specific icon
        if ext in self.extension_icons:
            return self.extension_icons[ext]
        
        # Fallback to default file icon
        return self.file_icon
    
    def setup_ui(self):
        """Setup the file display UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 5)
        layout.setSpacing(5)
        
        # Breadcrumb navigation - match sidebar title area height
        self.breadcrumb_frame = QFrame()
        self.breadcrumb_frame.setMinimumHeight(15)  # Match sidebar title + separator height
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_frame)
        self.breadcrumb_layout.setContentsMargins(5, 0, 5, 0)
        self.breadcrumb_layout.setSpacing(0)
        
        # Title label (similar to sidebar)
        self.breadcrumb_title = QLabel("Path :   ")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        self.breadcrumb_title.setFont(title_font)
        self.breadcrumb_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.breadcrumb_layout.addWidget(self.breadcrumb_title)
        
       
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
        
        # Create horizontal layout for toolbar and content
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Vertical toolbar on the left
        self.toolbar = VerticalToolbar()
        self.toolbar.zoom_in_requested.connect(self.zoom_in)
        self.toolbar.zoom_out_requested.connect(self.zoom_out)
        self.toolbar.foldersize_zero_requested.connect(self.on_foldersize_zero_clicked)
        self.toolbar.foldersize_one_requested.connect(self.on_foldersize_one_clicked)
        content_layout.addWidget(self.toolbar)
        
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
        self.file_list_widget = ClickableListWidget()
        self.file_list_widget.setViewMode(QListWidget.IconMode)
        self.file_list_widget.setResizeMode(QListWidget.Adjust)
        # Set initial grid and icon size based on zoom level
        self.update_zoom_level()
        
        # Store original sizes for calculation
        self.base_grid_size = QSize(120, 100)
        self.base_icon_size = QSize(64, 64)
        self.file_list_widget.setUniformItemSizes(True)
        self.file_list_widget.setWordWrap(True)
        self.file_list_widget.setSpacing(10)
        self.file_list_widget.itemClicked.connect(self.on_item_clicked)
        self.file_list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.file_list_widget.empty_area_clicked.connect(self.on_empty_area_clicked)
        self.content_widget.addWidget(self.file_list_widget)
        
        # Table view widget (for future detailed view)
        self.file_table_widget = QTableWidget()
        self.file_table_widget.setAlternatingRowColors(True)
        self.content_widget.addWidget(self.file_table_widget)
        
        # Set default to welcome page
        self.content_widget.setCurrentIndex(0)
        
        # Add content widget to horizontal layout
        content_layout.addWidget(self.content_widget)
        
        # Create container widget for the horizontal layout
        content_container = QWidget()
        content_container.setLayout(content_layout)
        layout.addWidget(content_container)
        
        # Initialize zoom level and button states
        self.update_zoom_level()
    
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
        """Load and display the contents of a directory using threaded loading"""
        # Cancel and cleanup any existing worker
        self._cleanup_worker()
        
        # Switch to file list view
        self.content_widget.setCurrentIndex(1)
        
        # Clear existing content
        self.file_list_widget.clear()
        
        # Start worker thread
        self.worker = DirectoryWorker(path)
        self.worker.contents_loaded.connect(self.on_contents_loaded)
        self.worker.error_occurred.connect(self.on_loading_error)
        self.worker.finished.connect(self.on_loading_finished)
        self.worker.start()
    
    def _cleanup_worker(self):
        """Safely cleanup the current worker thread"""
        if self.worker:
            # Cancel the worker
            self.worker.cancel()
            
            # Disconnect all signals to prevent issues during cleanup
            try:
                self.worker.contents_loaded.disconnect()
                self.worker.error_occurred.disconnect() 
                self.worker.finished.disconnect()
            except TypeError:
                # Signals might already be disconnected
                pass
            
            # Force termination if still running
            if self.worker.isRunning():
                self.worker.terminate()
                if not self.worker.wait(2000):  # Wait up to 2 seconds
                    print("Warning: Worker thread did not terminate cleanly")
            
            # Clean up the worker object
            self.worker.deleteLater()
            self.worker = None
    
    def on_contents_loaded(self, entries):
        """Handle successful directory contents loading"""
        # Add entries to the list
        for entry_name, is_dir, entry_path in entries:
            self.add_file_item(entry_name, is_dir, entry_path)
        
        # Emit directory changed signal to update details view with current directory
        if self.current_path:
            self.directory_changed.emit(self.current_path)
    
    def on_loading_error(self, error_message):
        """Handle directory loading error"""
        self.show_error(error_message)
    
    def on_loading_finished(self):
        """Handle completion of directory loading (success or error)"""
        # Don't cleanup worker here - let it be handled by _cleanup_worker() 
        # when the next operation starts, or when the widget is destroyed
    
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
        
        # Set icon based on type and extension
        if is_dir:
            item.setIcon(self.folder_icon)
        else:
            # Use extension-specific icon if available
            item.setIcon(self.get_icon_for_file(name))
        
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
    
    def on_item_clicked(self, item):
        """Handle single-click on file/folder items for selection"""
        data = item.data(Qt.UserRole)
        if not data:
            return
        
        # Emit selection signal for both files and folders
        file_path = data['path']
        self.file_selected.emit(file_path)
    
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
            # File double-clicked - could open file or show more details
            file_path = data['path']
            print(f"File double-clicked: {file_path}")
    
    def on_empty_area_clicked(self):
        """Handle clicks in empty areas of the file list widget"""
        # Clear any selection and show current directory in details view
        if self.current_path:
            # Emit directory changed signal to update details view with current directory
            self.directory_changed.emit(self.current_path)
    
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
    
    def get_zoom_level(self):
        """Get the current zoom level index"""
        return self.current_zoom_index
    
    def set_zoom_level(self, zoom_index):
        """Set the zoom level by index"""
        if 0 <= zoom_index < len(self.zoom_levels):
            self.current_zoom_index = zoom_index
            self.update_zoom_level()
    
    def restore_settings(self, current_path=None, zoom_level=None):
        """Restore settings from saved state"""
        # Restore zoom level
        if zoom_level is not None:
            self.set_zoom_level(zoom_level)
        
        # Restore current path if provided and valid
        if current_path and os.path.exists(current_path) and os.path.isdir(current_path):
            self.current_path = current_path
            self.update_breadcrumb(current_path)
            self.load_directory_contents(current_path)
    
    def zoom_in(self):
        """Increase the icon size (zoom in)"""
        if self.current_zoom_index < len(self.zoom_levels) - 1:
            self.current_zoom_index += 1
            self.update_zoom_level()
    
    def zoom_out(self):
        """Decrease the icon size (zoom out)"""
        if self.current_zoom_index > 0:
            self.current_zoom_index -= 1
            self.update_zoom_level()
    
    def update_zoom_level(self):
        """Update the icon and grid sizes based on current zoom level"""
        icon_size = self.zoom_levels[self.current_zoom_index]
        
        # Re-render SVG icons at the new size
        self.load_icons(icon_size)
        
        # Calculate grid size proportionally (add some padding)
        grid_width = icon_size + 56  # Base padding of 56px
        grid_height = icon_size + 36  # Base padding of 36px
        
        # Update the list widget
        self.file_list_widget.setIconSize(QSize(icon_size, icon_size))
        self.file_list_widget.setGridSize(QSize(grid_width, grid_height))
        
        # Update existing items with new icons
        self.update_existing_item_icons()
        
        # Update button states
        self.toolbar.zoom_in_btn.setEnabled(self.current_zoom_index < len(self.zoom_levels) - 1)
        self.toolbar.zoom_out_btn.setEnabled(self.current_zoom_index > 0)
    
    def update_existing_item_icons(self):
        """Update the icons of all existing items in the file list"""
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            if item:
                data = item.data(Qt.UserRole)
                if data:
                    # Update icon based on type and extension
                    if data.get('is_dir', False):
                        item.setIcon(self.folder_icon)
                    else:
                        # Use extension-specific icon if available
                        item.setIcon(self.get_icon_for_file(data.get('name', '')))
    
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
                separator.setStyleSheet("color: #666666; margin: 0 1px;")
                self.breadcrumb_container_layout.addWidget(separator)
            
            # Create the clickable button
            button = QPushButton(segment)
            button.setFlat(True)
            button.setStyleSheet("""
                QPushButton {
                    border: none;
                    padding: 0px 0px;
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

    def on_foldersize_zero_clicked(self):
        """Handle foldersize zero button click - delegate to folder size action"""
        foldersize_actions.on_foldersize_zero_clicked(self)
    
    def on_foldersize_one_clicked(self):
        """Handle foldersize one button click - build scan and resize folders"""
        foldersize_actions.on_foldersize_one_clicked(self) 