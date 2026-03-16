import json
import logging
from pathlib import Path
from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)

class AgentDefinition:
    def __init__(self, name, system_prompt, model=None, tools=None, icon="robot"):
        self.id = name.lower().replace(" ", "_")
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools or [] # List of tool names
        self.icon = icon

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "tools": self.tools,
            "icon": self.icon
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name", "Unknown"),
            system_prompt=data.get("system_prompt", ""),
            model=data.get("model"),
            tools=data.get("tools", []),
            icon=data.get("icon", "robot")
        )

class AgentManager:
    """Manages custom agent definitions and their persistence."""
    
    def __init__(self, storage_path=None):
        if storage_path is None:
            self.storage_path = CONFIG_DIR / "custom_agents.json"
        else:
            self.storage_path = Path(storage_path)
            
        self.agents = {}
        self._load_agents()

    def _load_agents(self):
        """Load agents from local JSON storage."""
        if not self.storage_path.exists():
            self._create_defaults()
            return
            
        try:
            data = json.loads(self.storage_path.read_text())
            for item in data:
                agent = AgentDefinition.from_dict(item)
                self.agents[agent.id] = agent
        except Exception as e:
            log.error(f"Failed to load agents: {e}")
            self._create_defaults()

    def _create_defaults(self):
        """Create a set of standard starter agents."""
        defaults = [
            AgentDefinition(
                "Code Architect",
                "You are an expert software architect. Focus on clean code, design patterns, and scalability.",
                icon="code"
            ),
            AgentDefinition(
                "Creative Writer",
                "You are a versatile creative writer. Help the user with storytelling, copy, and creative ideation.",
                icon="edit"
            ),
            AgentDefinition(
                "Security Auditor",
                "You are a cybersecurity expert. Analyze code for vulnerabilities and suggest best security practices.",
                icon="shield"
            )
        ]
        for a in defaults:
            self.agents[a.id] = a
        self.save_agents()

    def save_agents(self):
        """Persist current agents to disk."""
        try:
            data = [a.to_dict() for a in self.agents.values()]
            self.storage_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.error(f"Failed to save agents: {e}")

    def add_agent(self, agent_def):
        self.agents[agent_def.id] = agent_def
        self.save_agents()

    def delete_agent(self, agent_id):
        if agent_id in self.agents:
            del self.agents[agent_id]
            self.save_agents()
            return True
        return False

    def get_agent(self, agent_id):
        return self.agents.get(agent_id)

    def list_agents(self):
        return list(self.agents.values())
