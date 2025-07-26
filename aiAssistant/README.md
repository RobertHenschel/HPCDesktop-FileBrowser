# File Search AI Assistant

A Qt5-based chatbot that helps users search and analyze file system scan data using natural language queries. The assistant can automatically translate user questions into SQL queries and execute them against SQLite databases containing file metadata.

## Features

- **Natural Language Interface**: Ask questions in plain English about your file scans
- **Automatic SQL Generation**: The AI converts your questions into appropriate SQL queries
- **Database Schema Awareness**: Automatically understands database structure and relationships
- **Rich File Metadata**: Query file permissions, timestamps, sizes, Lustre metadata, and more
- **Qt5 GUI**: Modern, responsive user interface with colored message formatting

## Tools Available

The assistant has access to three main tools:

1. **get_available_directories**: Lists all scanned directories from available databases
2. **get_db_metadata**: Retrieves database schema and structure information
3. **run_sql_query**: Executes custom SQL queries on the file databases

## Example Queries

You can ask questions like:

- "What directories are available for searching?"
- "Show me the largest files in the BR200 database"
- "Find all executable files with permissions 755"
- "Which files were modified in the last week?"
- "Show me files with specific Lustre stripe configurations"
- "What's the total size of all Python files?"

## Database Schema

The system works with SQLite databases containing these main tables:

- **scan_info**: Information about directory scans
- **files**: Basic file information (path, size, type)
- **file_permissions**: Detailed permission bits and flags
- **file_ownership**: User and group ownership
- **file_timestamps**: Access, modify, and change times
- **file_inodes**: Inode numbers, device IDs, link counts
- **lustre_metadata**: Lustre-specific metadata (stripes, OSTs, etc.)
- **extended_attributes**: Extended file attributes and SELinux context
- **acl_info**: POSIX ACL information

## Setup and Usage

1. Ensure you have a `config.dat` file with your OpenAI API key:
   ```
   OpenAI = "your-api-key-here"
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the MCP server (in one terminal):
   ```bash
   cd aiAssistant
   python3 mcp_server.py
   ```

4. Start the AI assistant (in another terminal):
   ```bash
   python3 aiAssistant/ai_assistant.py
   ```

## Technical Architecture

- **Frontend**: Qt5-based GUI with threaded message processing
- **Backend**: OpenAI GPT-3.5-turbo for natural language understanding
- **Data Layer**: SQLite databases with file system metadata
- **Communication**: MCP (Model Context Protocol) server for tool execution

## Dependencies

- PyQt5 >= 5.15.0
- openai >= 1.0.0
- mcp >= 0.1.0
- qasync >= 0.23.0

The assistant intelligently combines these tools to provide comprehensive answers to your file system queries. 