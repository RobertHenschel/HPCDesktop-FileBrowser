#!/usr/bin/env python3
import sys
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMenuBar, QVBoxLayout, 
                             QHBoxLayout, QWidget, QSplitter, QAction)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon

from sidebar import Sidebar
from toolbar import Toolbar
from file_display import FileDisplay


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
        """Setup the main layout with toolbar and splitter"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Add toolbar
        self.toolbar = Toolbar()
        layout.addWidget(self.toolbar)
        
        # Create splitter for sidebar and file display
        splitter = QSplitter(Qt.Horizontal)
        
        # Create sidebar
        self.sidebar = Sidebar(self.filesystem_config)
        splitter.addWidget(self.sidebar)
        
        # Create file display area
        self.file_display = FileDisplay()
        splitter.addWidget(self.file_display)
        
        # Connect signals
        self.sidebar.filesystem_selected.connect(self.on_filesystem_selected)
        self.sidebar.add_current_path_requested.connect(self.on_add_current_path_requested)
        self.file_display.directory_changed.connect(self.on_directory_changed)
        self.toolbar.navigate_up.connect(self.on_navigate_up)
        self.toolbar.refresh_requested.connect(self.on_refresh_requested)
        
        # Set initial splitter sizes (sidebar: 300px, file display: rest)
        splitter.setSizes([300, 900])
        splitter.setStretchFactor(0, 0)  # Sidebar doesn't stretch
        splitter.setStretchFactor(1, 1)  # File display stretches
        
        layout.addWidget(splitter)
        
        # Restore saved settings
        self.restore_settings()
    
    def on_filesystem_selected(self, name, path):
        """Handle filesystem selection from sidebar"""
        print(f"Filesystem selected: {name} at {path}")
        
        # Expand user path for checking (path already has $USER expanded from config)
        expanded_path = os.path.expanduser(path)
        
        # Enable/disable navigation buttons
        parent_dir = os.path.dirname(expanded_path)
        can_go_up = parent_dir != expanded_path and os.path.exists(parent_dir)
        self.toolbar.enable_navigation(up=can_go_up)
        
        # Update sidebar with current path for the Add Current Path button
        self.sidebar.set_current_path(expanded_path)
        
        # Update file display
        self.file_display.set_filesystem(name, path)
    
    def on_directory_changed(self, new_path):
        """Handle directory navigation within file display"""
        print(f"Directory changed to: {new_path}")
        
        # Enable/disable navigation buttons
        parent_dir = os.path.dirname(new_path)
        can_go_up = parent_dir != new_path and os.path.exists(parent_dir)
        self.toolbar.enable_navigation(up=can_go_up)
        
        # Update sidebar with current path for the Add Current Path button
        self.sidebar.set_current_path(new_path)
    
    def on_navigate_up(self):
        """Handle navigate up button click"""
        current_path = self.file_display.get_current_path()
        if current_path:
            parent_path = os.path.dirname(current_path)
            if parent_path != current_path and os.path.exists(parent_path):
                self.file_display.current_path = parent_path
                self.file_display.update_breadcrumb(parent_path)
                self.file_display.load_directory_contents(parent_path)
    
    def on_refresh_requested(self):
        """Handle refresh button click"""
        self.file_display.refresh()
    
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
