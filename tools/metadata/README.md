# Tool Metadata Structure

## Overview

This document explains how tool metadata is structured to support tools with multiple commands.

## Problem

Many security tools (like `nmap`, `metasploit`, `sqlmap`) have multiple commands/operations, each with different parameters. For example:

- **nmap** has: `quick_scan`, `syn_scan`, `service_scan`, `vuln_scan`, etc.
- Each command has different parameters:
  - `quick_scan`: only needs `target`
  - `syn_scan`: needs `target` and `ports`
  - `service_scan`: needs `target` and `ports`

## Solution: Commands Structure

Each tool now has a `commands` field that contains all available commands, each with its own parameters schema.

## Metadata Structure

### Tool Definition

```json
{
  "name": "nmap",
  "description": "Network port scanner with service detection",
  "category": "recon",
  "priority": true,
  "assigned_agents": ["recon_agent"],
  "commands": {
    "quick_scan": {
      "description": "Fast scan of top 100 ports",
      "parameters": {
        "type": "object",
        "properties": {
          "target": {
            "type": "string",
            "description": "Target IP or hostname"
          }
        },
        "required": ["target"]
      },
      "timeout": 120,
      "requires_sudo": false,
      "output_format": "text"
    },
    "syn_scan": {
      "description": "TCP SYN stealth scan (requires root)",
      "parameters": {
        "type": "object",
        "properties": {
          "target": {
            "type": "string",
            "description": "Target IP or hostname"
          },
          "ports": {
            "type": "array",
            "description": "Port range or specific ports"
          }
        },
        "required": ["target"]
      },
      "timeout": 300,
      "requires_sudo": true,
      "output_format": "text"
    }
  },
  "risk_level": "low",
  "requires_auth": false
}
```

### Command Definition

Each command has:
- **description**: What this command does
- **parameters**: JSON schema for this command's parameters
- **timeout**: Execution timeout in seconds
- **requires_sudo**: Whether this command needs root privileges
- **output_format**: Expected output format (text, json, xml)

## How It Works

### 1. Tool Selection

When the AI agent needs to use a tool, it selects both:
- **Tool name**: `nmap`
- **Command name**: `quick_scan`

### 2. Function Calling Format

For Ollama function calling, each command becomes a separate function:

```
nmap:quick_scan
nmap:syn_scan
nmap:service_scan
```

### 3. Execution

The executor receives:
```python
{
    "tool_name": "nmap",
    "command_name": "quick_scan",
    "parameters": {
        "target": "192.168.1.1"
    }
}
```

### 4. Parameter Validation

Parameters are validated against the specific command's schema, not a generic tool schema.

## Backward Compatibility

Tools without commands (legacy format) still work:
- They use the `parameters` field directly
- The executor falls back to legacy parameters if no command is specified

## Source: rutx Repository

The tool definitions are extracted from the [rutx repository](https://github.com/LeHTVy/rutx.git), which defines tools with their commands using `ToolSpec` and `CommandTemplate`:

```python
ToolSpec(
    name="nmap",
    commands={
        "quick_scan": CommandTemplate(
            args=["-v", "-F", "{target}"],
            timeout=120
        ),
        "syn_scan": CommandTemplate(
            args=["-v", "-sS", "-p", "{ports}", "{target}"],
            timeout=300,
            requires_sudo=True
        )
    }
)
```

## Statistics

- **Total tools**: 186
- **Tools with commands**: 56 (from rutx)
- **Legacy tools**: 130 (single parameters schema)

## Benefits

1. **Precise Parameter Validation**: Each command validates only its required parameters
2. **Better AI Understanding**: AI can see all available commands and choose the right one
3. **Type Safety**: Each command has its own parameter types
4. **Documentation**: Command descriptions explain what each command does
5. **Execution Control**: Timeout and sudo requirements per command
