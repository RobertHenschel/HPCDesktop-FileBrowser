#!/usr/bin/env python3
import sys
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMenuBar, QVBoxLayout, 
                             QHBoxLayout, QWidget, QSplitter, QAction)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon

from sidebar import Sidebar
from file_display import FileDisplay
from details_view import DetailsView


class FileBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HPC Desktop File Browser")
        
        # Initialize settings
        self.settings = QSettings("HPCDesktop", "FileBrowser")
        
        # Load saved window geometry or use defaults
        geometry = self.settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.setGeometry(100, 100, 1200, 800)
        
        # Set application icon
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "filebrowser.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Load filesystem configuration
        self.load_filesystem_config()
        
        # Setup UI
        self.setup_menu_bar()
        self.setup_main_layout()
        
    def load_filesystem_config(self):
        """Load filesystem configuration from JSON file"""
        try:
            with open('filesystems.json', 'r') as f:
                self.filesystem_config = json.load(f)
            
            # Expand environment variables in paths
            self._expand_config_paths(self.filesystem_config)
            
        except FileNotFoundError:
            print("Warning: filesystems.json not found, using empty config")
            self.filesystem_config = {"toplevel": []}
        except json.JSONDecodeError:
            print("Warning: Invalid JSON in filesystems.json, using empty config")
            self.filesystem_config = {"toplevel": []}
    
    def _expand_config_paths(self, config):
        """Recursively expand environment variables in filesystem paths"""
        if isinstance(config, dict):
            if 'path' in config:
                # Expand environment variables like $USER
                config['path'] = os.path.expandvars(config['path'])
            
            # Recursively process nested structures
            for key, value in config.items():
                if isinstance(value, (dict, list)):
                    self._expand_config_paths(value)
        
        elif isinstance(config, list):
            for item in config:
                if isinstance(item, (dict, list)):
                    self._expand_config_paths(item)
    
    def setup_menu_bar(self):
        """Setup the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        refresh_action = QAction('Refresh', self)
        refresh_action.setShortcut('F5')
        view_menu.addAction(refresh_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        help_menu.addAction(about_action)
    
    def setup_main_layout(self):
        """Setup the main layout with details view and main content splitter"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove all margins
        layout.setSpacing(0)  # Remove spacing
        
        # Create vertical splitter for details view at top and main content below
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.setHandleWidth(2)  # Thinner splitter handle
        main_splitter.setContentsMargins(0, 0, 0, 0)  # Remove splitter margins
        
        # Create details view component
        self.details_view = DetailsView()
        main_splitter.addWidget(self.details_view)
        
        # Create horizontal splitter for sidebar and file display
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(2)
        content_splitter.setContentsMargins(0, 0, 0, 0)
        
        # Create sidebar
        self.sidebar = Sidebar(self.filesystem_config)
        self.details_view.set_sidebar(self.sidebar)
        content_splitter.addWidget(self.sidebar)
        
        # Create file display area
        self.file_display = FileDisplay()
        content_splitter.addWidget(self.file_display)
        
        # Add content splitter to main splitter
        main_splitter.addWidget(content_splitter)
        
        # Connect signals
        self.sidebar.filesystem_selected.connect(self.on_filesystem_selected)
        self.sidebar.add_current_path_requested.connect(self.on_add_current_path_requested)
        self.file_display.directory_changed.connect(self.on_directory_changed)
        
        # Connect details view signals
        self.file_display.directory_changed.connect(self.details_view.set_current_directory)
        self.file_display.file_selected.connect(self.on_file_selected)
        
        # Set initial content splitter sizes (sidebar: 300px, file display: rest)
        content_splitter.setSizes([250, 900])
        content_splitter.setStretchFactor(0, 0)  # Sidebar doesn't stretch
        content_splitter.setStretchFactor(1, 1)  # File display stretches
        
        # Set initial main splitter sizes (details view: 150px, content: rest)
        main_splitter.setSizes([150, 650])
        main_splitter.setStretchFactor(0, 0)  # Details view can be resized but doesn't auto-stretch
        main_splitter.setStretchFactor(1, 1)  # Content area stretches
        
        layout.addWidget(main_splitter)
        
        # Restore saved settings
        self.restore_settings()
    
    def on_filesystem_selected(self, name, path):
        """Handle filesystem selection from sidebar"""
        print(f"Filesystem selected: {name} at {path}")
        
        # Expand user path for checking (path already has $USER expanded from config)
        expanded_path = os.path.expanduser(path)
        
        # Note: Navigation is now handled via breadcrumb clicks
        
        # Update sidebar with current path for the Add Current Path button
        self.sidebar.set_current_path(expanded_path)
        
        # Update file display
        self.file_display.set_filesystem(name, path)
    
    def on_directory_changed(self, new_path):
        """Handle directory navigation within file display"""
        print(f"Directory changed to: {new_path}")
        
        # Note: Navigation is now handled via breadcrumb clicks
        
        # Update sidebar with current path for the Add Current Path button
        self.sidebar.set_current_path(new_path)
    
    def on_file_selected(self, file_path):
        """Handle file selection from file display"""
        print(f"File selected: {file_path}")
        
        # Update details view with selected file
        is_directory = os.path.isdir(file_path)
        self.details_view.set_selected_item(file_path, is_directory)
    
    def closeEvent(self, event):
        """Handle application close event"""
        # Save window geometry
        self.settings.setValue("window/geometry", self.saveGeometry())
        
        # Save current path and zoom level
        current_path = self.file_display.get_current_path()
        if current_path:
            self.settings.setValue("file_display/current_path", current_path)
        
        zoom_level = self.file_display.get_zoom_level()
        self.settings.setValue("file_display/zoom_level", zoom_level)
        
        # Save custom paths before closing
        self.sidebar.save_on_close()
        
        event.accept()
    
    def restore_settings(self):
        """Restore saved settings on application start"""
        # Restore current path and zoom level
        current_path = self.settings.value("file_display/current_path", "")
        zoom_level = self.settings.value("file_display/zoom_level", 2)  # Default to 64px
        
        # Convert zoom_level to int if it's a string
        if isinstance(zoom_level, str):
            zoom_level = int(zoom_level)
        
        # Restore file display settings
        self.file_display.restore_settings(current_path, zoom_level)
    
    def on_add_current_path_requested(self):
        """Handle request to add current path to custom paths"""
        current_path = self.file_display.get_current_path()
        if current_path:
            # Generate a name for the custom path (use the directory name)
            path_name = os.path.basename(current_path) or "Root"
            
            # If name is empty or just "/", use the parent directory name
            if not path_name or path_name == "/":
                parent_path = os.path.dirname(current_path)
                path_name = os.path.basename(parent_path) or "Root"
            
            # Make sure the name is unique
            existing_names = [cp['name'] for cp in self.sidebar.custom_paths]
            original_name = path_name
            counter = 1
            while path_name in existing_names:
                path_name = f"{original_name} ({counter})"
                counter += 1
            
            # Add the custom path to sidebar
            self.sidebar.add_custom_path(path_name, current_path)
            print(f"Added custom path: {path_name} -> {current_path}")


def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("HPC Desktop File Browser")
    app.setApplicationVersion("1.0")
    
    # Set global application icon
    icon_path = os.path.join(os.path.dirname(__file__), "resources", "filebrowser.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = FileBrowser()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
