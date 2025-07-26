#!/usr/bin/env python3
from PyQt5.QtWidgets import QWidget, QTabWidget, QTabBar, QLabel
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QFont, QColor, QPainterPath, QPixmap

class CustomTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setStyleSheet("QTabBar { background: transparent; }")
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(event.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        
        # Draw unselected tabs from right to left so left tabs overlap right tabs
        selected_index = self.currentIndex()
        for i in range(self.count() - 1, -1, -1):
            if i != selected_index:
                self.draw_tab(painter, i)
        if selected_index >= 0:
            self.draw_tab(painter, selected_index)
    
    def draw_tab(self, painter, index):
        rect = self.get_visual_tab_rect(index)
        is_selected = (index == self.currentIndex())
        colors = [(132, 197, 219), (144, 199, 170), (140, 144, 191), (212,183,175), (255,243,168), (171,148,176), (236,151,86), (255,223,76)]
        color = colors[index] if index < len(colors) else (120, 120, 120)
        
        # Create tab shape
        path = QPainterPath()
        if is_selected:
            top_y, bottom_y = rect.top() - 3, rect.bottom() + 2
            path.moveTo(rect.left() + 5, bottom_y)
            path.lineTo(rect.left() + 10, top_y + 8)
            path.lineTo(rect.left() + 15, top_y)
            path.lineTo(rect.right() - 15, top_y)
            path.lineTo(rect.right() - 10, top_y + 8)
            path.lineTo(rect.right() - 5, bottom_y)
        else:
            top_y, bottom_y = rect.top() + 2, rect.bottom() + 1
            path.moveTo(rect.left() + 3, bottom_y)
            path.lineTo(rect.left() + 8, top_y + 6)
            path.lineTo(rect.left() + 12, top_y)
            path.lineTo(rect.right() - 12, top_y)
            path.lineTo(rect.right() - 8, top_y + 6)
            path.lineTo(rect.right() - 3, bottom_y)
        path.closeSubpath()
        
        # Draw tab
        painter.setBrush(QColor(*color))
        painter.setPen(QColor(max(0, color[0] - 30), max(0, color[1] - 30), max(0, color[2] - 30)))
        painter.drawPath(path)
        
        # Draw text
        painter.setPen(QColor(0, 0, 0))
        painter.setFont(QFont("Arial", 10, QFont.Bold if is_selected else QFont.Normal))
        text_rect = QRect(rect.left() + 8, rect.top() + 4, rect.width() - 16, rect.height() - 8)
        painter.drawText(text_rect, Qt.AlignCenter, self.tabText(index))
    
    def tabSizeHint(self, index):
        text = self.tabText(index)
        font_metrics = self.fontMetrics()
        text_width = font_metrics.width(text)
        text_height = font_metrics.height()
        return QRect(0, 0, max(80, text_width + 40), text_height + 5).size()
    
    def get_visual_tab_rect(self, index):
        """Get the visual position where the tab should be drawn (overlapped)."""
        rect = super().tabRect(index)
        overlap_offset = 20 * index
        if index > 0:
            rect.moveLeft(rect.left() - overlap_offset)
        return rect
    
    def tabRect(self, index):
        """Get the original tab rectangle for proper hit testing."""
        return super().tabRect(index)
    
    def tabAt(self, pos):
        """Override tab hit testing to use visual positions."""
        for i in range(self.count()):
            visual_rect = self.get_visual_tab_rect(i)
            if visual_rect.contains(pos):
                return i
        return -1

class NotebookWidget(QTabWidget):
    def __init__(self, parent=None, tabs=None):
        super().__init__(parent)
        self.setTabPosition(QTabWidget.North)
        self.setTabBar(CustomTabBar())
        self.setStyleSheet("""
            QTabWidget { background: transparent; }
            QTabWidget::pane { border: 2px solid #888888; background-color: #f0f0f0; border-radius: 5px; margin-top: 0px; }
            QTabWidget::tab-bar { alignment: left; background: transparent; }
        """)
        
        # Tab colors (same as in CustomTabBar)
        self.tab_colors = [(132, 197, 219), (144, 199, 170), (140, 144, 191), (212,183,175), (255,243,168), (171,148,176), (236,151,86), (255,223,76)]
        
        # Create repair icon widget
        self.repair_icon = QLabel(self)
        self.repair_icon.setStyleSheet("background: transparent;")
        try:
            pixmap = QPixmap("./resources/repair.png")
            if not pixmap.isNull():
                # Size icon to match tab height (approximately 30 pixels)
                scaled_pixmap = pixmap.scaled(15, 15, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.repair_icon.setPixmap(scaled_pixmap)
            else:
                # Fallback if image doesn't load
                self.repair_icon.setText("🔧")
                self.repair_icon.setAlignment(Qt.AlignCenter)
        except Exception:
            # Fallback if there's any error loading the image
            self.repair_icon.setText("🔧")
            self.repair_icon.setAlignment(Qt.AlignCenter)
        
        self.repair_icon.setFixedSize(25, 25)
        self.repair_icon.show()
        
        # Create tabs
        if tabs:
            for name, widget in tabs:
                self.addTab(widget, name)
        else:
            # Default empty tabs
            for name in ["General", "Documents", "Demos", "Inbox"]:
                self.addTab(QWidget(), name)
        
        # Apply background colors to tab contents
        self.apply_tab_colors()
    
    def apply_tab_colors(self):
        """Apply matching background colors to tab content widgets"""
        for i in range(self.count()):
            widget = self.widget(i)
            if widget:
                color = self.tab_colors[i] if i < len(self.tab_colors) else (240, 240, 240)
                # Create a slightly lighter version of the tab color for the content
                lighter_color = (
                    min(255, color[0] + 20),
                    min(255, color[1] + 20),
                    min(255, color[2] + 20)
                )
                widget.setStyleSheet(f"""
                    QWidget {{
                        background-color: rgb({lighter_color[0]}, {lighter_color[1]}, {lighter_color[2]});
                    }}
                    QLabel {{
                        background-color: transparent;
                    }}
                    QScrollArea {{
                        background-color: transparent;
                        border: none;
                    }}
                """)
    
    def addTab(self, widget, label):
        """Override addTab to apply colors to new tabs"""
        index = super().addTab(widget, label)
        if widget:
            color = self.tab_colors[index] if index < len(self.tab_colors) else (240, 240, 240)
            # Create a slightly lighter version of the tab color for the content
            lighter_color = (
                min(255, color[0] + 20),
                min(255, color[1] + 20),
                min(255, color[2] + 20)
            )
            widget.setStyleSheet(f"""
                QWidget {{
                    background-color: rgb({lighter_color[0]}, {lighter_color[1]}, {lighter_color[2]});
                }}
                QLabel {{
                    background-color: transparent;
                }}
                QScrollArea {{
                    background-color: transparent;
                    border: none;
                }}
            """)
        return index
    
    def resizeEvent(self, event):
        """Override resize event to position the repair icon next to the tabs"""
        super().resizeEvent(event)
        
        # Position the repair icon to the right of the tabs
        tab_bar = self.tabBar()
        if tab_bar and self.repair_icon:
            # Calculate position: to the right of all tabs with some margin
            last_tab_right = 0
            if tab_bar.count() > 0:
                last_tab_rect = tab_bar.get_visual_tab_rect(tab_bar.count() - 1)
                last_tab_right = last_tab_rect.right()
            
            # Position icon with 10px margin from last tab
            icon_x = last_tab_right + 50
            # Adjust vertical position to better align with the visual center of the tabs
            icon_y = (tab_bar.height() - self.repair_icon.height()) // 2 + 3 + 9
            
            self.repair_icon.move(icon_x, icon_y)

    def paintEvent(self, event):
        """Override paint event to draw the selected tab indicator line across content width."""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get current selected tab
        current_index = self.currentIndex()
        if current_index >= 0:
            # Get the color for the selected tab
            color = self.tab_colors[current_index] if current_index < len(self.tab_colors) else (120, 120, 120)
            
            # Calculate the line position (right at tab bar bottom, no gap)
            tab_bar = self.tabBar()
            line_y = tab_bar.height()  # Position right at tab bar bottom
            
            # Draw the 5-pixel line respecting content margins (5px left/right)
            line_start_x = 5
            line_width = self.width() - 10  # 5px margin on each side
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*color))
            painter.drawRect(line_start_x, line_y, line_width, 5) 