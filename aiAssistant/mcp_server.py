#!/usr/bin/env python3

import os
import sqlite3
import json
from mcp.server.fastmcp import FastMCP as MCDPServer, Context as ToolContext

# Create the server instance first
# Tools will be registered to this instance via decorators
server = MCDPServer(name="dirscanInterfaceServer")

@server.tool()
async def get_db_metadata(ctx: ToolContext, db: str) -> str:
    """Returns metadata about a database."""
    print(f"[MCP Server] Tool call: get_db_metadata, db: {db}")
    try:
        # check if db.json exists in the same directory as the db
        if os.path.exists(f"../dirscans/{db}.json"):
            with open(f"../dirscans/{db}.json", "r") as f:
                return f.read()
        else:
            return f"Error: {db}.json does not exist in ../dirscans"
    except Exception as e:
        print(f"[MCP Server] Error getting metadata for {db}: {e}")
        return f"Error getting metadata: {str(e)}"

@server.tool()
async def run_sql_query(ctx: ToolContext, db: str, query: str) -> str:
    """Executes a SQL query on the specified database and returns the results."""
    print(f"[MCP Server] Tool call: run_sql_query, db: {db}, query: {query}")
    try:
        db_path = f"../dirscans/{db}.sqlite3"
        if not os.path.exists(db_path):
            return f"Error: Database {db}.sqlite3 does not exist in ../dirscans"
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Execute the query
        cursor.execute(query)
        
        # Get column names
        column_names = [description[0] for description in cursor.description] if cursor.description else []
        
        # Fetch results
        results = cursor.fetchall()
        conn.close()
        
        # Format results as JSON for easy parsing
        if not results:
            return "Query executed successfully but returned no results."
        
        # Convert results to list of dictionaries
        formatted_results = []
        for row in results:
            row_dict = {}
            for i, value in enumerate(row):
                row_dict[column_names[i]] = value
            formatted_results.append(row_dict)
        
        # Return JSON string with metadata
        response = {
            "status": "success",
            "row_count": len(results),
            "columns": column_names,
            "results": formatted_results[:100]  # Limit to first 100 rows for safety
        }
        
        if len(results) > 100:
            response["note"] = f"Results limited to first 100 rows. Total rows: {len(results)}"
        
        return json.dumps(response, indent=2)
        
    except sqlite3.Error as e:
        print(f"[MCP Server] SQL Error: {e}")
        return f"SQL Error: {str(e)}"
    except Exception as e:
        print(f"[MCP Server] Error running SQL query: {e}")
        return f"Error running SQL query: {str(e)}"

@server.tool()
async def get_available_directories(ctx: ToolContext) -> str:
    """Lists available directories in the database."""
    print(f"[MCP Server] Tool call: get_available_directories")
    try:
        # Find all *.sqlite3 files in the dirscans directory
        sqlite_files = [f for f in os.listdir("../dirscans") if f.endswith(".sqlite3")]
        # print files found to console
        print(f"[MCP Server] Found {len(sqlite_files)} SQLite files: {sqlite_files}")
        directories = []
        # Open them to find the directory name
        for file in sqlite_files:
            conn = sqlite3.connect(f"../dirscans/{file}")
            cursor = conn.cursor()
            cursor.execute("SELECT directory FROM scan_info")
            directory = cursor.fetchone()
            if directory:
                directories.append(directory[0])  # fetchone returns a tuple
                print(f"[MCP Server] Directory: {directory[0]}")
            conn.close()
        return directories
    except Exception as e:
        print(f"[MCP Server] Error getting available directories: {e}")
        return f"Error getting available directories: {str(e)}"

# Make main synchronous
def main(): 
    print("[MCP Server] Starting directory scan interfaceMCP server...")
    print("[MCP Server] Registered tools: get_available_directories, get_db_metadata, run_sql_query")
    # Call server.run() directly. It's expected to be a blocking call that manages its own event loop.
    server.run(transport="sse")

if __name__ == "__main__":
    # Call the synchronous main function directly
    main() 