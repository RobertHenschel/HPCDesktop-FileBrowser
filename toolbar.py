from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QToolBar, QPushButton, 
                             QLabel, QLineEdit, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon


class Toolbar(QWidget):
    # Signals for future functionality
    navigate_back = pyqtSignal()
    navigate_forward = pyqtSignal()
    navigate_up = pyqtSignal()
    refresh_requested = pyqtSignal()
    path_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the toolbar UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Navigation buttons (disabled for now)
        self.back_button = QPushButton("←")
        self.back_button.setToolTip("Go Back")
        self.back_button.setEnabled(False)
        self.back_button.setFixedSize(30, 30)
        layout.addWidget(self.back_button)
        
        self.forward_button = QPushButton("→")
        self.forward_button.setToolTip("Go Forward")
        self.forward_button.setEnabled(False)
        self.forward_button.setFixedSize(30, 30)
        layout.addWidget(self.forward_button)
        
        self.up_button = QPushButton("↑")
        self.up_button.setToolTip("Go Up")
        self.up_button.setEnabled(False)
        self.up_button.setFixedSize(30, 30)
        layout.addWidget(self.up_button)
        
        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator1)
        
        # Refresh button
        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setToolTip("Refresh")
        self.refresh_button.setFixedSize(30, 30)
        layout.addWidget(self.refresh_button)
        
        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator2)
        
        # Path label
        path_label = QLabel("Path:")
        layout.addWidget(path_label)
        
        # Path display/input
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select a filesystem from the sidebar")
        self.path_input.setReadOnly(True)  # Make read-only for now
        layout.addWidget(self.path_input)
        
        # Add stretch to push everything to the left
        layout.addStretch()
        
        # Set fixed height for toolbar
        self.setFixedHeight(50)
        
        # Connect signals (for future use)
        self.back_button.clicked.connect(self.navigate_back.emit)
        self.forward_button.clicked.connect(self.navigate_forward.emit)
        self.up_button.clicked.connect(self.navigate_up.emit)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.path_input.returnPressed.connect(self.on_path_entered)
    
    def on_path_entered(self):
        """Handle path input when user presses Enter"""
        path = self.path_input.text().strip()
        if path:
            self.path_changed.emit(path)
    
    def set_current_path(self, path):
        """Set the current path in the toolbar"""
        self.path_input.setText(path)
    
    def enable_navigation(self, back=False, forward=False, up=False):
        """Enable/disable navigation buttons"""
        self.back_button.setEnabled(back)
        self.forward_button.setEnabled(forward)
        self.up_button.setEnabled(up)
    
    def set_path_editable(self, editable=True):
        """Make the path input editable or read-only"""
        self.path_input.setReadOnly(not editable) 