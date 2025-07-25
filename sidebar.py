import json
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QLabel, QFrame, QPushButton, QMenu, QAction)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class Sidebar(QWidget):
    # Signal emitted when a filesystem is selected
    filesystem_selected = pyqtSignal(str, str)  # name, path
    # Signal emitted when user wants to add current path
    add_current_path_requested = pyqtSignal()
    
    def __init__(self, filesystem_config):
        super().__init__()
        self.filesystem_config = filesystem_config
        self.custom_paths = []  # Store custom paths for current session
        self.config_file = os.path.expanduser("~/.filebrowserconfig")
        self._updating_tree = False  # Flag to prevent recursive operations
        self.add_path_button = None  # Will be created in custom paths widget
        self.load_custom_paths()  # Load saved custom paths
        self.setup_ui()
        self.populate_tree()
    
    def setup_ui(self):
        """Setup the sidebar UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 5)
        layout.setSpacing(5)
        
        # Title area to match file display header height
        title_frame = QFrame()
        title_frame.setMinimumHeight(15)  # Adjusted to match exactly
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)
        
        # Title label
        title_label = QLabel("File Systems")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(title_label)
        
        layout.addWidget(title_frame)
        
        # Tree widget for filesystem hierarchy
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setRootIsDecorated(True)
        self.tree_widget.setIndentation(20)
        
        # Enable context menu
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.on_context_menu)
        
        # Connect signals
        self.tree_widget.itemClicked.connect(self.on_item_clicked)
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree_widget.itemChanged.connect(self.on_item_changed)
        
        layout.addWidget(self.tree_widget)
        
        # Set minimum width
        self.setMinimumWidth(250)
    
    def populate_tree(self):
        """Populate the tree widget with filesystem data"""
        # Prevent multiple simultaneous calls
        if self._updating_tree:
            return
            
        # Set flag to prevent recursive operations
        self._updating_tree = True
        
        # Temporarily disconnect the itemChanged signal to prevent recursion during initial population
        try:
            self.tree_widget.itemChanged.disconnect(self.on_item_changed)
        except:
            pass  # Signal might not be connected yet during initial setup
        
        try:
            self.tree_widget.clear()
            
            # Add regular filesystem categories
            for toplevel_item in self.filesystem_config.get('toplevel', []):
                category = toplevel_item.get('category', 'Unknown Category')
                filesystems = toplevel_item.get('filesystems', [])
                
                # Create top-level category item
                category_item = QTreeWidgetItem(self.tree_widget)
                category_item.setText(0, category)
                category_item.setData(0, Qt.UserRole, {'type': 'category', 'category': category})
                
                # Set bold font for category
                font = category_item.font(0)
                font.setBold(True)
                category_item.setFont(0, font)
                
                # Add filesystem items and subcategories under this category
                self._populate_filesystems(category_item, filesystems, category)
                
                # Expand category by default
                category_item.setExpanded(True)
            
            # Always add custom paths category (even if empty)
            self._add_custom_paths_category()
        finally:
            # Reconnect the signal and clear the flag
            self.tree_widget.itemChanged.connect(self.on_item_changed)
            self._updating_tree = False
    
    def _populate_filesystems(self, parent_item, filesystems, parent_category):
        """Recursively populate filesystem items and subcategories"""
        for item in filesystems:
            if 'category' in item:
                # This is a subcategory
                subcategory = item.get('category', 'Unknown Category')
                sub_filesystems = item.get('filesystems', [])
                
                # Create subcategory item
                subcategory_item = QTreeWidgetItem(parent_item)
                subcategory_item.setText(0, subcategory)
                subcategory_item.setData(0, Qt.UserRole, {
                    'type': 'category', 
                    'category': subcategory,
                    'parent_category': parent_category
                })
                
                # Set bold font for subcategory
                font = subcategory_item.font(0)
                font.setBold(True)
                subcategory_item.setFont(0, font)
                
                # Recursively add items under this subcategory
                self._populate_filesystems(subcategory_item, sub_filesystems, subcategory)
                
                # Expand subcategory by default
                subcategory_item.setExpanded(True)
                
            else:
                # This is a regular filesystem item
                name = item.get('name', 'Unknown')
                path = item.get('path', '')
                
                filesystem_item = QTreeWidgetItem(parent_item)
                filesystem_item.setText(0, name)
                filesystem_item.setData(0, Qt.UserRole, {
                    'type': 'filesystem',
                    'name': name,
                    'path': path,
                    'category': parent_category
                })
                
                # Set tooltip with path information
                filesystem_item.setToolTip(0, f"Path: {path}")
    
    def on_item_clicked(self, item, column):
        """Handle item click"""
        data = item.data(0, Qt.UserRole)
        if data and data.get('type') == 'filesystem':
            name = data.get('name', '')
            path = data.get('path', '')
            print(f"Selected filesystem: {name} ({path})")
            # Emit signal to navigate immediately on single click
            self.filesystem_selected.emit(name, path)
    
    def on_item_double_clicked(self, item, column):
        """Handle item double-click"""
        data = item.data(0, Qt.UserRole)
        if data:
            if data.get('type') == 'category':
                # Toggle expansion for category items
                item.setExpanded(not item.isExpanded())
            # For filesystem items, single click already handles navigation
            # so double-click doesn't need to do anything extra
    
    def refresh(self):
        """Refresh the sidebar contents"""
        self.populate_tree()
    
    def get_selected_filesystem(self):
        """Get currently selected filesystem data"""
        current_item = self.tree_widget.currentItem()
        if current_item:
            data = current_item.data(0, Qt.UserRole)
            if data and data.get('type') == 'filesystem':
                return data
        return None
    
    def on_add_current_path(self):
        """Handle Add Current Path button click"""
        # Always emit signal - main window will handle current path validation
        self.add_current_path_requested.emit()
    
    def add_custom_path(self, name, path):
        """Add a custom path to the custom paths section"""
        # Add to our custom paths list
        custom_entry = {'name': name, 'path': path}
        self.custom_paths.append(custom_entry)
        
        # Save the updated custom paths to file
        self.save_custom_paths()
        
        # Simply rebuild the entire tree - cleaner and avoids recursion
        self.populate_tree()
    
    def create_custom_paths_widget(self):
        """Create a custom widget with 'Custom Paths' label and '+' button"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 4, 0)  # Small right margin for button
        layout.setSpacing(5)
        
        # "Custom Paths" label
        label = QLabel("Custom Paths")
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)
        
        # Add stretch to push button to the right
        layout.addStretch()
        
        # "+" button
        self.add_path_button = QPushButton("+")
        self.add_path_button.setFixedSize(16, 16)
        self.add_path_button.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
                text-align: center;
                padding: 1px 0px 3px 0px;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:pressed {
                background-color: #003d82;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.add_path_button.clicked.connect(self.on_add_current_path)
        # Button is always enabled - will use current path from details view
        layout.addWidget(self.add_path_button)
        
        return widget
    
    def _add_custom_paths_category(self):
        """Add the Custom Paths category to the tree"""
        # Create custom paths category item
        custom_category_item = QTreeWidgetItem(self.tree_widget)
        custom_category_item.setData(0, Qt.UserRole, {'type': 'category', 'category': 'Custom Paths'})
        
        # Set custom widget with label and button
        custom_widget = self.create_custom_paths_widget()
        self.tree_widget.setItemWidget(custom_category_item, 0, custom_widget)
        
        # Add all custom paths under this category
        for custom_path in self.custom_paths:
            custom_item = QTreeWidgetItem(custom_category_item)
            custom_item.setText(0, custom_path['name'])
            custom_item.setData(0, Qt.UserRole, {
                'type': 'filesystem',
                'name': custom_path['name'],
                'path': custom_path['path'],
                'category': 'Custom Paths',
                'is_custom': True
            })
            
            # Set tooltip with path information
            custom_item.setToolTip(0, f"Custom Path: {custom_path['path']}")
        
        # Expand the custom paths category
        custom_category_item.setExpanded(True)
    
    def _refresh_custom_paths_category(self):
        """Refresh the custom paths category in the tree"""
        # This method is now replaced by populate_tree() calls
        # Keeping it for backward compatibility but just delegate to populate_tree
        self.populate_tree()
    
    def set_current_path(self, path):
        """Set the current path and update the Add Current Path button tooltip"""
        self.current_path = path if path and path.strip() else ""
        if self.add_path_button:  # Check if button exists (created in custom widget)
            if self.current_path:
                self.add_path_button.setToolTip(f"Add current path: {self.current_path}")
            else:
                self.add_path_button.setToolTip("Add current path (no path selected)")
    
    def load_custom_paths(self):
        """Load custom paths from the configuration file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    self.custom_paths = config_data.get('custom_paths', [])
                    print(f"Loaded {len(self.custom_paths)} custom paths from {self.config_file}")
            else:
                print(f"No configuration file found at {self.config_file}")
        except Exception as e:
            print(f"Error loading custom paths: {e}")
            self.custom_paths = []
    
    def save_custom_paths(self):
        """Save custom paths to the configuration file"""
        try:
            config_data = {
                'custom_paths': self.custom_paths
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
                
            print(f"Saved {len(self.custom_paths)} custom paths to {self.config_file}")
            
        except Exception as e:
            print(f"Error saving custom paths: {e}")
    
    def sync_custom_paths_from_tree(self):
        """Sync the custom_paths list to match what's currently displayed in the tree"""
        # Find the Custom Paths category in the tree
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            category_item = root.child(i)
            category_data = category_item.data(0, Qt.UserRole)
            if category_data and category_data.get('category') == 'Custom Paths':
                # Update our custom_paths list to match the tree
                self.custom_paths.clear()
                for j in range(category_item.childCount()):
                    child_item = category_item.child(j)
                    child_data = child_item.data(0, Qt.UserRole)
                    if child_data and child_data.get('is_custom'):
                        self.custom_paths.append({
                            'name': child_item.text(0),  # Use current display text
                            'path': child_data.get('path', '')
                        })
                break
    
    def save_on_close(self):
        """Save custom paths when the application is closing"""
        print("Saving custom paths on application close")
        self.sync_custom_paths_from_tree()
        self.save_custom_paths()
    
    def on_context_menu(self, position):
        """Handle right-click context menu"""
        item = self.tree_widget.itemAt(position)
        if not item:
            return
        
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        
        # Only show context menu for custom paths
        if data.get('type') == 'filesystem' and data.get('is_custom', False):
            context_menu = QMenu(self)
            
            rename_action = QAction("Rename", self)
            rename_action.triggered.connect(lambda: self.rename_custom_path(item))
            context_menu.addAction(rename_action)
            
            delete_action = QAction("Delete", self)
            delete_action.triggered.connect(lambda: self.delete_custom_path(item))
            context_menu.addAction(delete_action)
            
            # Show the context menu at the cursor position
            context_menu.exec_(self.tree_widget.mapToGlobal(position))
    
    def delete_custom_path(self, item):
        """Delete a custom path"""
        data = item.data(0, Qt.UserRole)
        if not data or not data.get('is_custom', False):
            return
        
        path_to_delete = data.get('path', '')
        name_to_delete = data.get('name', '')
        
        # Remove from custom_paths list
        self.custom_paths = [cp for cp in self.custom_paths if cp['path'] != path_to_delete]
        
        print(f"Deleted custom path: {name_to_delete} -> {path_to_delete}")
        
        # Save the updated custom paths to file
        self.save_custom_paths()
        
        # Simply rebuild the entire tree - cleaner and avoids recursion
        self.populate_tree()
    
    def rename_custom_path(self, item):
        """Enable inline editing for renaming a custom path"""
        data = item.data(0, Qt.UserRole)
        if not data or not data.get('is_custom', False):
            return
        
        # Just make the item editable and start editing - let Qt handle it
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.tree_widget.editItem(item, 0)
    
    def on_item_changed(self, item, column):
        """Handle when an item's text is changed (after inline editing)"""
        # Prevent recursive operations during tree updates
        if self._updating_tree:
            return
        
        # Just sync the custom_paths list to match what's displayed in the tree
        self.sync_custom_paths_from_tree() 

    def find_filesystem_for_path(self, path):
        """Return the file system dict whose path is a prefix of the given path, or None if not found."""
        # Flatten all file system entries (including custom paths)
        def collect_filesystems(filesystems, out):
            for item in filesystems:
                if 'category' in item:
                    collect_filesystems(item.get('filesystems', []), out)
                else:
                    out.append(item)
        all_filesystems = []
        collect_filesystems(self.filesystem_config.get('toplevel', []), all_filesystems)
        # Add custom paths
        for cp in self.custom_paths:
            all_filesystems.append({'name': cp['name'], 'path': cp['path'], 'is_custom': True})
        # Find the best match (longest prefix)
        best_match = None
        best_len = -1
        for fs in all_filesystems:
            fs_path = os.path.expanduser(fs.get('path', ''))
            if path.startswith(fs_path) and len(fs_path) > best_len:
                best_match = fs
                best_len = len(fs_path)
        return best_match 