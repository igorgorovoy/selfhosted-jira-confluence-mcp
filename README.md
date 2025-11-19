# Selfhosted Jira & Confluence MCP Server

MCP (Model Context Protocol) server for self-hosted Jira Server/Data Center 8.x and Confluence Server/Data Center 6.x.

## 🚀 Features

### Confluence Tools

- **`confluence_get_spaces`** - Get list of all Confluence spaces
- **`confluence_get_page`** - Get page by ID with full content
- **`confluence_search_pages`** - Search pages using CQL (Confluence Query Language)
- **`confluence_create_page`** - Create new page with storage format content

### Jira Tools

- **`jira_get_issue`** - Get issue by key
- **`jira_search_issues`** - Search issues using JQL (Jira Query Language)
- **`jira_create_issue`** - Create new issue

## 📋 Requirements

- Python 3.12+
- Self-hosted Jira Server/Data Center 8.x
- Self-hosted Confluence Server/Data Center 6.x
- API tokens for both systems

## 🔧 Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd selfhosted-jira-confluence-mcp
```

2. Create virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create `.env` file with your credentials:
```bash
# Confluence Configuration
CONFLUENCE_BASE_URL=https://confluence.example.com
CONFLUENCE_USERNAME=your-username
CONFLUENCE_API_TOKEN=your-api-token

# Jira Configuration
JIRA_BASE_URL=https://jira.example.com
JIRA_USERNAME=your-username
JIRA_API_TOKEN=your-api-token
```

## 🔌 Connecting to Cursor

1. Add configuration to `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "atlassian-jira-confluence": {
      "command": "/absolute/path/to/your/project/venv/bin/python",
      "args": [
        "/absolute/path/to/your/project/server.py"
      ],
      "cwd": "/absolute/path/to/your/project"
    }
  }
}
```

2. Restart Cursor completely:
   - On macOS: `⌘ + Q` and reopen
   - On Windows/Linux: Close and reopen the application

3. The MCP server will start automatically and be available in chat

## 💡 Usage Examples

### Confluence

**Get list of spaces:**
```
Use confluence_get_spaces to get all spaces
```

**Search pages:**
```
Find all pages in DEV space: space = "DEV" AND type = "page"
```

**Get specific page:**
```
Show page with ID 12345
```

**Create new page:**
```
Create page in space "DEV" with title "My New Page" and content "<p>Hello World</p>"
```

### Jira

**Search issues:**
```
Find all open tasks in L2S project: project = L2S AND statusCategory != Done
```

**Get specific issue:**
```
Show details of issue L2S-123
```

**Create new issue:**
```
Create task in project L2S with summary "Fix bug"
```

## 🧪 Testing

Run the test script to verify Confluence connection:

```bash
source venv/bin/activate
python test_spaces.py
```

This will fetch and display all available Confluence spaces.

## 🛠️ Development

### Option 1: Direct Python execution

The server can be run directly for testing:

```bash
source venv/bin/activate
python server.py
```

This starts the MCP server in STDIO mode. The server will wait for input on stdin and write responses to stdout. Press `Ctrl+C` to stop.

**Note**: When running directly, the server expects MCP protocol messages on stdin. For actual testing with Confluence/Jira, use the integration method below or the test scripts.

### Option 2: Integration testing with Cursor

For real-world testing, configure the server in Cursor (see "🔌 Connecting to Cursor" section above). The server will start automatically when Cursor launches and will be available through the AI chat interface.

This is the recommended way to test the server with actual Confluence and Jira operations.

### Option 3: Development mode with MCP CLI (optional)

If you have the `mcp` CLI tool installed globally:

```bash
~/.default-venv/bin/mcp dev server.py
```

This will start the MCP server in development mode with inspector UI for debugging.

## 📚 API References

### Confluence REST API
- Base path: `/rest/api`
- Compatible with: Confluence Server/Data Center 6.14.1+
- [Official Documentation](https://docs.atlassian.com/atlassian-confluence/REST/6.14.1/)

### Jira REST API
- Base path: `/rest/api/2`
- Compatible with: Jira Server/Data Center 8.8.0+
- [Official Documentation](https://docs.atlassian.com/software/jira/docs/api/REST/8.8.0/)

## 🔐 Security Notes

- Store credentials in `.env` file (never commit this file)
- Use API tokens instead of passwords
- The `.env` file is ignored by git (see `.gitignore`)
- API tokens can be generated from your Atlassian profile settings

## 🐛 Troubleshooting

**MCP server doesn't start:**
- Check that `.env` file exists and contains valid credentials
- Verify Python path in `mcp.json` is correct and absolute
- Check Cursor Developer Console (`⌘ + Shift + I`) for errors

**Connection errors:**
- Verify base URLs are correct (without trailing slashes)
- Check network connectivity to Jira/Confluence servers
- Ensure API tokens are valid and not expired

**Tools not appearing in Cursor:**
- Restart Cursor completely
- Check MCP settings in Cursor preferences
- Verify `mcp.json` syntax is valid JSON

## 📝 License

MIT

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## 👨‍💻 Author

Igor Gorovyy