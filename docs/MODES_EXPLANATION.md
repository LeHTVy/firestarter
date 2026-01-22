# Execution Modes Explanation

## What are Execution Modes?

Execution modes (`config/modes.yaml`) are a **safety mechanism** that controls which tools can be executed based on their aggressiveness level. This is **NOT related to model selection** - it's about tool execution safety.

## Why Do We Need Modes?

Different penetration testing scenarios require different levels of aggressiveness:

1. **Passive Mode**: Only OSINT tools (no packets sent, legally safe)
   - Use cases: Public information gathering, legal compliance testing
   - Example tools: `whois_lookup`, `dns_enum`, `web_search`

2. **Cooperative Mode**: Scanner tools allowed (authenticated scan, limited scope)
   - Use cases: Authorized network scanning, vulnerability assessment
   - Example tools: `nmap_scan`, `ssl_cert_scan`, `port_scan`

3. **Simulation Mode**: All tools allowed (lab/digital twin, no production impact)
   - Use cases: Safe exploit testing, attack chain replay
   - Example tools: `metasploit_exploit`, `sql_injection_test`, `xss_test`

## How It Works

1. Each tool in `tools/metadata/tools.json` has a `mode` field:
   ```json
   {
     "name": "nmap_scan",
     "mode": ["active"],
     ...
   }
   ```

2. Mode Manager checks if tool's mode is compatible with current execution mode:
   - Passive mode: Only allows `["passive"]` tools
   - Cooperative mode: Allows `["passive", "active"]` tools
   - Simulation mode: Allows `["passive", "active", "destructive"]` tools

3. If tool is not compatible, it's filtered out (unless user explicitly requests it)

## Can I Disable Mode Checking?

Yes, you have several options:

### Option 1: Set Default Mode to Simulation (Allows All Tools)

Edit `config/modes.yaml`:
```yaml
default_mode: "simulation"  # Change from "cooperative" to "simulation"
```

### Option 2: Disable Mode Check in Code

In `agents/pentest_graph.py`, comment out the mode check:
```python
# Check mode compatibility
# if tool.mode and not self.mode_manager.is_tool_compatible(tool.mode, conversation_id):
#     policy_issues.append(...)
#     continue
```

### Option 3: Remove Mode Field from Tools

If you remove the `mode` field from tools in `tools/metadata/tools.json`, mode checking will be skipped (backward compatibility).

## Current Behavior

- **Default mode**: `cooperative` (allows passive + active tools)
- **Direct tool commands**: If user explicitly requests a tool (e.g., "run nmap on target"), mode check is bypassed with a warning
- **Automatic tool selection**: Mode check is enforced for safety

## Recommendation

Keep mode checking enabled for safety, but use `simulation` mode if you want full flexibility:
```yaml
default_mode: "simulation"
```

This allows all tools while still maintaining the safety mechanism structure.
