import logging
import os
import re
import xml.etree.ElementTree as ET
from string import Template
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Matches {identifier} for f-string-style placeholders (identifier = letter/underscore + alnum)
# Avoids matching JSON braces like "NAME": { by requiring a valid identifier after {
_FSTR_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class AgentDefinitionReader:
    """
    Reads agent and task definitions from an XML file.

    Expected structure:

    <agent-definitions>
      <agents>
        <agent id="preprocessor" verbose="true" allowDelegation="false">
          <role>...</role>
          <goal>...</goal>
          <backstory>...</backstory>
          <tasks>
            <task id="preprocessing">
              <description>...</description>
              <expectedOutput>...</expectedOutput>
            </task>
          </tasks>
        </agent>
        ...
      </agents>
    </agent-definitions>
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        if config_path is None:
            config_path = os.getenv(
                "AGENT_DEFINITION_PATH", "/app/config/agent-definition.xml"
            )

        self.config_path = config_path
        self._agents: Dict[str, Dict[str, Any]] = {}

        if os.path.exists(self.config_path):
            logger.info(
                "Reading agent definition templates from XML: path=%s",
                self.config_path,
            )
            try:
                tree = ET.parse(self.config_path)
                root = tree.getroot()
                self._load_agents(root)
            except Exception:
                # Fail silently and fall back to code defaults if XML is invalid
                self._agents = {}

    def _load_agents(self, root: ET.Element) -> None:
        agents_root = root.find("agents")
        if agents_root is None:
            return

        for agent_el in agents_root.findall("agent"):
            agent_id = agent_el.get("id")
            if not agent_id:
                continue

            role_el = agent_el.find("role")
            goal_el = agent_el.find("goal")
            backstory_el = agent_el.find("backstory")

            tasks: Dict[str, Dict[str, str]] = {}
            tasks_root = agent_el.find("tasks")
            if tasks_root is not None:
                for task_el in tasks_root.findall("task"):
                    task_id = task_el.get("id")
                    if not task_id:
                        continue
                    desc_el = task_el.find("description")
                    expected_el = task_el.find("expectedOutput")
                    tasks[task_id] = {
                        "description": (desc_el.text or "").strip() if desc_el is not None else "",
                        "expected_output": (expected_el.text or "").strip() if expected_el is not None else "",
                    }

            self._agents[agent_id] = {
                "role": (role_el.text or "").strip() if role_el is not None else "",
                "goal": (goal_el.text or "").strip() if goal_el is not None else "",
                "backstory": (backstory_el.text or "").strip() if backstory_el is not None else "",
                "verbose": agent_el.get("verbose"),
                "allow_delegation": agent_el.get("allowDelegation"),
                "tasks": tasks,
            }

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Return the config dict for a given agent id."""
        logger.info("Reading agent definition template from XML: agent_id=%s", agent_id)
        return self._agents.get(agent_id, {})

    def get_task(self, agent_id: str, task_id: str) -> Dict[str, str]:
        """Return the config dict for a task belonging to an agent."""
        logger.info(
            "Reading task definition template from XML: agent_id=%s, task_id=%s",
            agent_id,
            task_id,
        )
        agent_cfg = self._agents.get(agent_id, {})
        tasks = agent_cfg.get("tasks") or {}
        return tasks.get(task_id, {})


def render_template(template: Optional[str], context: Optional[Dict[str, Any]] = None) -> str:
    """
    Render template with variable substitution, supporting both:
    - ${var} (Template style)
    - {var} (f-string style)

    Only {identifier} patterns are replaced; literal braces in JSON (e.g. "name": {)
    are left unchanged. Produces the same output as Python f-strings for simple vars.
    """
    if not template:
        return ""
    ctx = context or {}
    logger.info("Agent Definition Template (Before processing):\n%s", template)
    logger.info("Agent Definition Template Parameters:\n%s", ctx)
    # 1. Process ${var} placeholders (string.Template)
    result = Template(template).safe_substitute(ctx)
    # 2. Process {var} placeholders (f-string style)
    result = _FSTR_PATTERN.sub(
        lambda m: str(ctx.get(m.group(1), m.group(0))), result
    )
    logger.info("Agent Definition (After processing template):\n%s", result)
    return result

