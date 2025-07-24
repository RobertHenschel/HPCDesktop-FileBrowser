import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette


class DetailsView(QWidget):
    """Details view component that shows information about the current directory or selected file/folder"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = ""
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the details view UI"""
        # Set pastel blue background
        self.setStyleSheet("""
            QWidget {
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Placeholder label for now
        self.info_label = QLabel("Details View - No item selected")
        self.info_label.setStyleSheet("color: #666666; font-style: italic;")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)
        
        # Set minimum height
        self.setMinimumHeight(100)
        
    def set_current_directory(self, path):
        """Update the details view with information about the current directory"""
        self.current_path = path
        if path:
            self.info_label.setText(f"Current Directory: {path}")
            self.info_label.setStyleSheet("color: #333333;")
        else:
            self.info_label.setText("Details View - No directory selected")
            self.info_label.setStyleSheet("color: #666666; font-style: italic;")
    
    def set_selected_item(self, path, is_directory=False):
        """Update the details view with information about a selected file or folder"""
        self.current_path = path
        if path:
            item_type = "Directory" if is_directory else "File"
            filename = os.path.basename(path)
            self.info_label.setText(f"Selected {item_type}: {filename}")
            self.info_label.setStyleSheet("color: #333333;")
        else:
            self.info_label.setText("Details View - No item selected")
            self.info_label.setStyleSheet("color: #666666; font-style: italic;")
    
    def clear(self):
        """Clear the details view"""
        self.current_path = ""
        self.info_label.setText("Details View - No item selected")
        self.info_label.setStyleSheet("color: #666666; font-style: italic;") 