#!/usr/bin/env python3
"""
Demo script for the new MCP CLI commands.
"""

import subprocess
import sys

def run_command(cmd, description):
    """Run a command and display it."""
    print(f"\n{'='*70}")
    print(f"📋 {description}")
    print(f"{'='*70}")
    print(f"$ {cmd}")
    print()
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    return result.returncode == 0

def main():
    print("=" * 70)
    print("MCP CLI Commands Demo")
    print("=" * 70)
    
    commands = [
        (
            "loco mcp --help",
            "Show all available MCP commands"
        ),
        (
            "loco mcp list",
            "List all configured MCP servers"
        ),
        (
            "loco mcp show github-test",
            "Show detailed configuration (with masked secrets)"
        ),
        (
            "loco mcp add-json demo-fs '{\"type\":\"command\",\"command\":[\"npx\",\"-y\",\"@modelcontextprotocol/server-filesystem\"],\"args\":[\"/tmp\"]}'",
            "Add a filesystem MCP server"
        ),
        (
            "loco mcp list",
            "See the newly added server"
        ),
        (
            "loco mcp remove demo-fs",
            "Remove the demo server"
        ),
        (
            "loco mcp list",
            "Verify it was removed"
        ),
    ]
    
    for cmd, desc in commands:
        if not run_command(cmd, desc):
            print(f"\n❌ Command failed: {cmd}")
            sys.exit(1)
        input("\n[Press Enter to continue...]")
    
    print("\n" + "=" * 70)
    print("✅ Demo completed successfully!")
    print("=" * 70)
    
    print("""
Summary of MCP Commands:

  loco mcp list              List all configured servers
  loco mcp add-json <name>   Add a new server from JSON config
  loco mcp remove <name>     Remove a server
  loco mcp show <name>       Show detailed config (masks secrets)
  loco mcp test [name]       Test server connectivity
  loco mcp tools [name]      List available tools from server(s)

For more info: loco mcp --help
    """)

if __name__ == "__main__":
    main()
