import os
import pwd
import grp
import stat
import datetime
import platform
import subprocess
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QScrollArea
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette

from nsNotebook import NotebookWidget


class ClickableLabel(QLabel):
    """A clickable label that calls a function when clicked"""
    def __init__(self, text, click_handler, parent=None):
        super().__init__(text, parent)
        self.click_handler = click_handler
        self.setStyleSheet("color: #0066cc; text-decoration: underline; background-color: transparent; margin: 2px 0px;")
        self.setCursor(Qt.PointingHandCursor)
        self.setWordWrap(True)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.click_handler(self.text())
        super().mousePressEvent(event)


class DetailsView(QWidget):
    """Details view component that shows information about the current directory or selected file/folder"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = ""
        self.sidebar = None  # Reference to Sidebar for live queries
        self.setup_ui()

    def set_sidebar(self, sidebar):
        """Set the Sidebar instance for live queries."""
        self.sidebar = sidebar
    
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
        self.insights_tab = self.create_insights_tab()
        
        tabs = [
            ("Overview", self.general_tab),
            ("ACL", self.properties_tab),
            ("Extended Attributes", self.details_tab),
            ("Insights", self.insights_tab)
        ]
        
        # Create notebook widget with custom tabs
        self.notebook = NotebookWidget(tabs=tabs, details_view=self)
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
    
    def create_insights_tab(self):
        """Create the insights tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(3)  # Reduce spacing between labels

        # Title label
        title_label = QLabel("<b>Run Search Queries:</b>")
        title_label.setStyleSheet("color: #333333; background-color: transparent;")
        layout.addWidget(title_label)
        
        # Store clickable labels for later updates
        self.insights_labels = []
        
        # Create clickable labels for each query
        queries = [
            "What files and folders are not owned by me?",
            "What files and folders can I not delete?", 
            "What files have not been accessed in the last 30 days?",
            "What directory has the most files?",
            "What are the 10 largest files?"
        ]
        
        for query in queries:
            label = ClickableLabel(f"  {query}", self.handle_insights_click)
            self.insights_labels.append(label)
            layout.addWidget(label)
        
        layout.addStretch()
        return widget
    
    def handle_insights_click(self, query_text):
        """Handle clicks on insights query labels"""
        # Remove the leading spaces from the query text
        clean_query = query_text.strip()
        print(f"Insights query clicked: {clean_query}")
        print(f"Current directory: {self.current_path}")
        # Add your custom logic here - you can call other functions, 
        # emit signals, show dialogs, etc.
        # Load metadata for BR200 path.
        subprocess.Popen(["python3", "ai_assistant.py", "--batch", f'"Load metadata for short path BR200;{clean_query}"'], cwd="./aiAssistant")
        return clean_query
        
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
                file_sizes = sum(os.path.getsize(os.path.join(path, item)) for item in items if os.path.isfile(os.path.join(path, item)))
                # convert file_sizes to a human readable format
                if file_sizes < 1024:
                    file_sizes = f"{file_sizes} bytes"
                elif file_sizes < 1024 * 1024:
                    file_sizes = f"{file_sizes / 1024:.1f} KB"
                elif file_sizes < 1024 * 1024 * 1024:
                    file_sizes = f"{file_sizes / (1024 * 1024):.1f} MB"
                else:
                    file_sizes = f"{file_sizes / (1024 * 1024 * 1024):.1f} GB"
            except PermissionError:
                total_items = files_count = dirs_count = "Permission denied"
            # get the GID and UID of the directory
            gid = stat_info.st_gid
            uid = stat_info.st_uid
            # get the name of the user and group from the GID and UID            
            user = pwd.getpwuid(uid).pw_name
            group = grp.getgrgid(gid).gr_name
            group_members = grp.getgrgid(gid).gr_mem

            # Live query the sidebar for the file system info
            file_system = None
            if self.sidebar:
                file_system = self.sidebar.find_filesystem_for_path(path)
            fs_display = file_system['name'] if file_system and 'name' in file_system else 'Unknown'

            # Permissions and human readable permissions
            mode = stat_info.st_mode
            permissions = stat.filemode(mode)
            
            # Build user permissions string
            user_perms = []
            if mode & stat.S_IRUSR:
                user_perms.append("read")
            if mode & stat.S_IWUSR:
                user_perms.append("write") 
            if mode & stat.S_IXUSR:
                user_perms.append("execute")
            if len(user_perms) > 0:
                user_can = f"{'/'.join(user_perms)}"
            else:
                user_can = "None"
            
            # Build group permissions string
            group_perms = []
            if mode & stat.S_IRGRP:
                group_perms.append("read")
            if mode & stat.S_IWGRP:
                group_perms.append("write") 
            if mode & stat.S_IXGRP:
                group_perms.append("execute")
            if len(group_perms) > 0:
                group_can = f"{'/'.join(group_perms)}"
            else:
                group_can = "None"

            # Build other permissions string
            other_perms = []
            if mode & stat.S_IROTH:
                other_perms.append("read")
            if mode & stat.S_IWOTH:
                other_perms.append("write") 
            if mode & stat.S_IXOTH: 
                other_perms.append("execute")
            if len(other_perms) > 0:
                other_can = f"{'/'.join(other_perms)}"
            else:
                other_can = "None"
            
            # truncate path as needed, make it no longer than 50, put "..." in the middle if needed
            if len(path) > 40:
                path_display = path[:20] + "..." + path[-20:]
            else:
                path_display = path
            
            # turn group_members into a list of strings, make sure the final string is no longer than 40 characters
            group_members_display = ""
            for member in group_members:
                group_members_display += f"{member}, "
            # remove the last comma
            group_members_display = group_members_display[:-2]
            if len(group_members_display) > 40:
                group_members_display = group_members_display[:20] + "..." + group_members_display[-20:]

            # Count hidden files and folders
            hidden_files = sum(1 for item in items if item.startswith('.') and os.path.isfile(os.path.join(path, item)))
            hidden_dirs = sum(1 for item in items if os.path.isdir(os.path.join(path, item)) and item.startswith('.'))

            # check for ACLs on the current directory
            # if platform is Linux, set ACL support to true
            if platform.system() == 'Linux':
                acl_support = True
            else:
                acl_support = False
            if acl_support:
                try:
                    import posix1e
                    acl = posix1e.ACL(file=path)
                    # Check for extended ACL entries beyond the standard owner/group/other permissions
                    # Standard entries are: ACL_USER_OBJ, ACL_GROUP_OBJ, ACL_OTHER, ACL_MASK
                    # Extended ACLs have tag types: ACL_USER, ACL_GROUP
                    has_acls = False
                    for entry in acl:
                        if entry.tag_type in (posix1e.ACL_USER, posix1e.ACL_GROUP):
                            has_acls = True
                            break
                    if has_acls:
                        print(f"ACLs present on directory: {path}")
                except Exception as e:
                    # If pylibacl library is not available or error occurs, do nothing
                    print(f"Error checking for ACLs on directory: {path}: {str(e)}")
                    pass


            # Overview tab
            if not acl_support:
                acl_display = "Not Supported"
            else:
                # Format ACL display with conditional coloring
                if has_acls is True:
                    acl_display = '<span style="color: red; font-weight: bold;">Yes</span>'
                elif has_acls is False:
                    acl_display = 'No'
            
            general_text = f"""<table border=\"0\" cellspacing=\"0\" cellpadding=\"0\" style=\"border:none\">
<tr><td><b>File System:</b></td><td style=\"padding-left: 10px; padding-right: 10px\">{fs_display}</td><td style=\"padding-left: 10px\"><b>Owner:</b></td><td style=\"padding-left: 10px\">{user} ({uid})</td><td style=\"padding-left: 10px\"><b>Access Permissions:</b></td><td style=\"padding-left: 10px\">{permissions}</td></tr>
<tr><td><b>Directory:</b></td><td style=\"padding-left: 10px; padding-right: 10px\">{dir_name}</td><td style=\"padding-left: 10px\"><b>Owner Group:</b></td><td style=\"padding-left: 10px\">{group} ({gid})</td><td style=\"padding-left: 10px\"><b>User/Owner:</b></td><td style=\"padding-left: 10px\">{user_can}</td></tr>
<tr><td><b>Path:</b></td><td style=\"padding-left: 10px; padding-right: 10px\">{path_display}</td><td style=\"padding-left: 10px\"><b>Group Members:</b></td><td style=\"padding-left: 10px\">{group_members_display}</td><td style=\"padding-left: 10px\"><b>Group:</b></td><td style=\"padding-left: 10px\">{group_can}</td></tr>
<tr><td><b>Contents:</b></td><td style=\"padding-left: 10px; padding-right: 10px\" colspan=\"3\">{total_items} items ({dirs_count} folders, {files_count} files) {file_sizes}</td><td style=\"padding-left: 10px\"><b>Others:</b></td><td style=\"padding-left: 10px\">{other_can}</td></tr>
<tr><td><b>Hidden:</b></td><td style=\"padding-left: 10px; padding-right: 10px\" colspan=\"3\">{hidden_files+hidden_dirs} items ({hidden_dirs} folders, {hidden_files} files)</td><td style=\"padding-left: 10px\"><b>ACLs:</b></td><td style=\"padding-left: 10px\">{acl_display}</td></tr>
</table>"""
            self.general_label.setText(general_text)
            self.general_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # ACL tab
            created = datetime.datetime.fromtimestamp(stat_info.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            modified = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            accessed = datetime.datetime.fromtimestamp(stat_info.st_atime).strftime("%Y-%m-%d %H:%M:%S")
            
            # Print the ACL info if available, otherwise show a message
            if acl_support:
                try:
                    import posix1e
                    acl = posix1e.ACL(file=path)
                    if acl:
                        acl_html = str(acl)
                        properties_text = f"""<b>ACL:</b><pre style="font-family:monospace">{acl_html}</pre>"""
                    else:
                        properties_text = "<b>ACL:</b><br>No ACL entries found."
                except Exception as e:
                    properties_text = f"<b>ACL:</b><br>Error reading ACL: {str(e)}"
            else:
                properties_text = "<b>ACL:</b><br>Not supported on this platform."
            self.properties_label.setText(properties_text)
            self.properties_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # Extended Attributes tab
            details_text = f"""<b>Full Path:</b> {os.path.abspath(path)}
<br><b>Parent Directory:</b> {os.path.dirname(path)}
<br><b>Type:</b> Directory
<br><b>Inode:</b> {stat_info.st_ino}
<br><b>Device:</b> {stat_info.st_dev}"""
            self.details_label.setText(details_text)
            self.details_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # Insights tab - now uses persistent clickable labels, no updates needed


            
        except Exception as e:
            error_text = f"<b>Error reading directory:</b> {str(e)}"
            self.general_label.setText(error_text)
            self.properties_label.setText(error_text)
            self.details_label.setText(error_text)
    
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
            
            # Overview tab
            general_text = f"""<b>File:</b> {filename}
<br><b>Path:</b> {path}
<br><b>Size:</b> {size_str}
<br><b>Type:</b> {file_type} file"""
            self.general_label.setText(general_text)
            self.general_label.setStyleSheet("color: #333333; background-color: transparent;")
            
            # ACL tab
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
            
            # Extended Attributes tab
            details_text = f"""<b>Full Path:</b> {os.path.abspath(path)}
<br><b>Directory:</b> {os.path.dirname(path)}
<br><b>Filename:</b> {os.path.splitext(filename)[0]}
<br><b>Extension:</b> {ext or 'None'}
<br><b>Type:</b> Regular file
<br><b>Inode:</b> {stat_info.st_ino}
<br><b>Device:</b> {stat_info.st_dev}"""
            self.details_label.setText(details_text)
            self.details_label.setStyleSheet("color: #333333; background-color: transparent;")
            

                
        except Exception as e:
            error_text = f"<b>Error reading file:</b> {str(e)}"
            self.general_label.setText(error_text)
            self.properties_label.setText(error_text)
            self.details_label.setText(error_text)
    
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
    
    def clear(self):
        """Clear the details view"""
        self.current_path = ""
        self.clear_info() 