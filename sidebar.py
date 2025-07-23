from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QLabel, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class Sidebar(QWidget):
    # Signal emitted when a filesystem is selected
    filesystem_selected = pyqtSignal(str, str)  # name, path
    
    def __init__(self, filesystem_config):
        super().__init__()
        self.filesystem_config = filesystem_config
        self.setup_ui()
        self.populate_tree()
    
    def setup_ui(self):
        """Setup the sidebar UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Title area to match file display header height
        title_frame = QFrame()
        title_frame.setMinimumHeight(35)  # Adjusted to match exactly
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
        
        # Connect signals
        self.tree_widget.itemClicked.connect(self.on_item_clicked)
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout.addWidget(self.tree_widget)
        
        # Set minimum width
        self.setMinimumWidth(250)
    
    def populate_tree(self):
        """Populate the tree widget with filesystem data"""
        self.tree_widget.clear()
        
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
            # Future: emit signal for main window to handle
            # self.filesystem_selected.emit(name, path)
    
    def on_item_double_clicked(self, item, column):
        """Handle item double-click"""
        data = item.data(0, Qt.UserRole)
        if data:
            if data.get('type') == 'category':
                # Toggle expansion for category items
                item.setExpanded(not item.isExpanded())
            elif data.get('type') == 'filesystem':
                # Double-click on filesystem could trigger navigation
                name = data.get('name', '')
                path = data.get('path', '')
                print(f"Double-clicked filesystem: {name} ({path})")
                self.filesystem_selected.emit(name, path)
    
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