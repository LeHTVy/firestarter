# Role-based prompts for SNODE Pentest Agent

from pathlib import Path

# Prompt directory
PROMPTS_DIR = Path(__file__).parent
ROLES_DIR = PROMPTS_DIR / "roles"

# Role prompt files
PLANNER_PROMPT = ROLES_DIR / "planner.jinja2"
EXECUTOR_PROMPT = ROLES_DIR / "executor.jinja2"
ANALYZER_PROMPT = ROLES_DIR / "analyzer.jinja2"
BASE_PROMPT = PROMPTS_DIR / "snode_base.jinja2"
