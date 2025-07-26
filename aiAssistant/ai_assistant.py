#!/usr/bin/env python3

import sys
import re
import json
import asyncio
import qasync
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                           QHBoxLayout, QWidget, QTextEdit, QLineEdit, 
                           QPushButton, QSplitter, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCharFormat, QColor, QTextCursor
from openai import OpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client

# --- Configuration and API Key --- #

def read_api_key_from_config(config_path='./config.dat'):
    try:
        with open(config_path, 'r') as config_file:
            content = config_file.read()
            match = re.search(r'OpenAI\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
            else:
                print("Error: Could not find OpenAI key in config.dat")
                return None
    except FileNotFoundError:
        print(f"Error: config.dat not found at {config_path}")
        return None
    except Exception as e:
        print(f"Error reading config file: {str(e)}")
        return None

API_KEY = read_api_key_from_config()
if API_KEY:
    OPENAI_CLIENT = OpenAI(api_key=API_KEY)
else:
    OPENAI_CLIENT = None

# --- MCP Client Functions --- #

async def call_mcp_tool(tool_name: str, arguments: dict):
    mcp_server_url = "http://localhost:8000/sse"
    try:
        async with sse_client(mcp_server_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                if result.content and isinstance(result.content, list) and result.content[0].text:
                    return result.content[0].text
                return "Tool executed, but no specific text content returned."
    except ConnectionRefusedError:
        return f"Error: Could not connect to MCP Server at {mcp_server_url}. Is it running?"
    except Exception as e:
        return f"Error calling MCP tool '{tool_name}': {str(e)}"

# --- OpenAI Chatbot Logic --- #

SYSTEM_PROMPT = ("You are a helpful file search assistant that can help users find information about scanned directories and databases. "
                 "You have access to three main tools: "
                 "1. 'get_available_directories' - Lists all available scanned directories from SQLite databases "
                 "2. 'get_db_metadata' - Gets detailed metadata about a specific database including schema information "
                 "3. 'run_sql_query' - Executes SQL queries on databases to answer specific questions "
                 ""
                 "WORKFLOW: "
                 "- When users ask about available directories or databases, use get_available_directories first "
                 "- Before you write a SQL query, always get the database schema first using get_db_metadata "
                 "- When they ask specific questions about files, permissions, sizes, dates, etc., write and execute SQL queries using run_sql_query "
                 ""
                 "SQL QUERY GUIDELINES: "
                 "- Always get the database schema first using get_db_metadata before writing complex queries "
                 "- Use JOIN statements to combine data from related tables (files, file_permissions, file_timestamps, lustre_metadata, etc.) "
                 "- The main tables are: files, file_permissions, file_ownership, file_timestamps, file_inodes, lustre_metadata, extended_attributes, acl_info "
                 "- Always use proper table aliases and be specific about which database to query "
                 "- Format dates and file sizes in human-readable format when possible "
                 "- Limit results appropriately (the tool already limits to 100 rows) "
                 ""
                 "Be helpful and provide clear, well-formatted information based on the query results.")

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "get_available_directories",
            "description": "Lists all available scanned directories from SQLite databases.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_db_metadata",
            "description": "Gets detailed metadata about a specific database including schema and structure information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "db": {"type": "string", "description": "The database name (without .sqlite3 extension)"}
                },
                "required": ["db"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql_query",
            "description": "Executes a SQL query on the specified database and returns formatted results. Use this to answer specific questions about files, permissions, sizes, dates, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "db": {"type": "string", "description": "The database name (without .sqlite3 extension)"},
                    "query": {"type": "string", "description": "The SQL query to execute. Should be a valid SQLite query."}
                },
                "required": ["db", "query"]
            }
        }
    }
]

# --- Qt5 GUI Application --- #

class ChatMessage:
    def __init__(self, sender, content, message_type="normal"):
        self.sender = sender
        self.content = content
        self.message_type = message_type  # normal, tool_call, tool_response, error

class ChatWorker(QThread):
    message_received = pyqtSignal(str, str, str)  # sender, content, type
    
    def __init__(self, user_input, message_history):
        super().__init__()
        self.user_input = user_input
        self.message_history = message_history.copy()
        
    def run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.process_message())
        
    async def process_message(self):
        try:
            self.message_history.append({"role": "user", "content": self.user_input})
            
            response = OPENAI_CLIENT.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=self.message_history,
                tools=TOOLS_DEFINITION,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            self.message_history.append(message)
            
            if message.tool_calls:
                self.message_received.emit("Bot", "Let me check that for you...", "normal")
                
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    tool_call_info = f"Calling: {function_name}({function_args})"
                    self.message_received.emit("Tool", tool_call_info, "tool_call")
                    
                    # Call MCP server
                    tool_result = await call_mcp_tool(function_name, function_args)
                    
                    # Format SQL query results nicely
                    if function_name == "run_sql_query":
                        try:
                            result_data = json.loads(tool_result)
                            if result_data.get("status") == "success":
                                tool_response_info = f"Query returned {result_data.get('row_count', 0)} rows"
                                if "note" in result_data:
                                    tool_response_info += f" ({result_data['note']})"
                            else:
                                tool_response_info = f"Result: {tool_result}"
                        except:
                            tool_response_info = f"Result: {tool_result}"
                    else:
                        tool_response_info = f"Result: {tool_result}"
                        
                    self.message_received.emit("Tool", tool_response_info, "tool_response")
                    
                    self.message_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": str(tool_result)
                    })
                
                # Get follow-up response
                follow_up_response = OPENAI_CLIENT.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=self.message_history
                )
                final_message = follow_up_response.choices[0].message.content
                self.message_history.append(follow_up_response.choices[0].message)
                self.message_received.emit("Bot", final_message, "normal")
                
            else:
                bot_reply = message.content
                self.message_received.emit("Bot", bot_reply, "normal")
                
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.message_received.emit("Error", error_msg, "error")

class FileSearchChatbot(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Search Chatbot")
        self.setGeometry(100, 100, 800, 600)
        
        if not OPENAI_CLIENT:
            QMessageBox.critical(self, "Startup Error", 
                               "OpenAI client could not be initialized. Please check API key and config.dat.")
            sys.exit(1)
            
        self.message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.setup_ui()
        self.add_message("Bot", "Hello! I can help you search for information about scanned directories and databases. What would you like to know?", "normal")
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Chat display area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Consolas", 10))
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask about available directories or databases...")
        self.input_field.returnPressed.connect(self.send_message)
        
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        
        # Add to main layout
        main_layout.addWidget(self.chat_display, 1)
        main_layout.addLayout(input_layout)
        
        # Style the chat display
        self.setup_chat_styles()
        
    def setup_chat_styles(self):
        # Set up text formats for different message types
        self.user_format = QTextCharFormat()
        self.user_format.setForeground(QColor("blue"))
        self.user_format.setFontWeight(QFont.Bold)
        
        self.bot_format = QTextCharFormat()
        self.bot_format.setForeground(QColor("green"))
        self.bot_format.setFontWeight(QFont.Bold)
        
        self.tool_call_format = QTextCharFormat()
        self.tool_call_format.setForeground(QColor("purple"))
        self.tool_call_format.setFontItalic(True)
        
        self.tool_response_format = QTextCharFormat()
        self.tool_response_format.setForeground(QColor("orange"))
        self.tool_response_format.setFontItalic(True)
        
        self.error_format = QTextCharFormat()
        self.error_format.setForeground(QColor("red"))
        self.error_format.setFontWeight(QFont.Bold)
        
    def add_message(self, sender, content, message_type):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Choose format based on sender and type
        if sender == "User":
            format_to_use = self.user_format
        elif sender == "Bot":
            format_to_use = self.bot_format
        elif sender == "Tool" and message_type == "tool_call":
            format_to_use = self.tool_call_format
        elif sender == "Tool" and message_type == "tool_response":
            format_to_use = self.tool_response_format
        elif sender == "Error":
            format_to_use = self.error_format
        else:
            format_to_use = QTextCharFormat()
            
        # Add sender prefix for non-tool messages
        if message_type not in ["tool_call", "tool_response"]:
            cursor.insertText(f"{sender}: ", format_to_use)
            
        # Add message content
        normal_format = QTextCharFormat()
        if message_type in ["tool_call", "tool_response"]:
            cursor.insertText(f"  {content}\n", format_to_use)
        else:
            cursor.insertText(f"{content}\n", normal_format)
            
        cursor.insertText("\n")
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
        
    def send_message(self):
        user_input = self.input_field.text().strip()
        if not user_input:
            return
            
        # Add user message to display
        self.add_message("User", user_input, "normal")
        self.input_field.clear()
        
        # Disable input while processing
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        
        # Start worker thread for chat processing
        self.worker = ChatWorker(user_input, self.message_history)
        self.worker.message_received.connect(self.on_message_received)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.start()
        
    def on_message_received(self, sender, content, message_type):
        self.add_message(sender, content, message_type)
        
    def on_processing_finished(self):
        # Update message history with the worker's updated history
        self.message_history = self.worker.message_history
        
        # Re-enable input
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.setFocus()

def main():
    app = QApplication(sys.argv)
    
    if not API_KEY:
        QMessageBox.critical(None, "Startup Error", 
                           "OpenAI API key not found. Please check config.dat")
        sys.exit(1)
    
    window = FileSearchChatbot()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
