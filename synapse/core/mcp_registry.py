# MCP Server Registry - Curated list of high-value MCP servers

MCP_REGISTRY = [
    {
        "id": "github",
        "name": "GitHub",
        "description": "Expose GitHub repositories, issues, and PRs to Synapse. Manage your code directly from chat.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env_required": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        "icon": "github"
    },
    {
        "id": "postgres",
        "name": "PostgreSQL",
        "description": "Connect to your Postgres databases. Query schemas, tables, and data to help you write better SQL.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "env_required": ["DATABASE_URL"],
        "icon": "database"
    },
    {
        "id": "slack",
        "name": "Slack",
        "description": "Search messages, channels, and interact with your workspace. Bring your communication into the context.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env_required": ["SLACK_BOT_TOKEN"],
        "icon": "message"
    },
    {
        "id": "google_drive",
        "name": "Google Drive",
        "description": "Read and search your documents and files in Google Drive. Perfect for documentation and research.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-google-drive"],
        "icon": "folder"
    },
    {
        "id": "fetch",
        "name": "Web Fetch",
        "description": "Robust tool for fetching and summarizing web content. Handles JavaScript-heavy sites better than basic tools.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],
        "icon": "globe"
    },
    {
        "id": "filesystem",
        "name": "Local Filesystem",
        "description": "Provides secure, granular access to your local files and directories outside the current workspace.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home"],
        "icon": "file-directory"
    },
    {
        "id": "memory",
        "name": "Memory (Knowledge Graph)",
        "description": "An MCP server that provides a knowledge graph-based persistent memory system using local storage.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "icon": "brain"
    },
        {
        "id": "git",
        "name": "Git Ops",
        "description": "Enhanced Git operations tool. Perform commits, branches, and diffs with structural understanding.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-git"],
        "icon": "git-branch"
    },
    {
        "id": "brave_search",
        "name": "Brave Search",
        "description": "Privacy-focused web search directly from the agent. Get real-time answers without tracking.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env_required": ["BRAVE_API_KEY"],
        "icon": "search"
    },
    {
        "id": "everything",
        "name": "The 'Everything' Server",
        "description": "A playground server that exposes a wide variety of tools, resources, and templates for testing and fun.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-everything"],
        "icon": "star"
    }
]
