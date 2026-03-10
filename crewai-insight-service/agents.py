from crewai import Agent, LLM
from utils.config_parser import ConfigParser
from utils.agent_definition_reader import AgentDefinitionReader, render_template
import os


class InsightAgents:
    def __init__(self):
        config_path = os.getenv("CONFIG_PATH", "/app/config/agent-config.xml")
        self.config = ConfigParser(config_path)
        settings = self.config.get_settings()
        profiles = self.config.get_profiles()

        self.ollama_base_url = settings.get(
            "ollamaBaseUrl", "http://host.docker.internal:11434"
        )

        # Determine models based on profile
        active_profile = settings.get("modelProfile", "small")
        profile_data = profiles.get(active_profile, profiles.get("small", {}))

        self.light_model_name = profile_data.get("light", "mistral")
        self.heavy_model_name = profile_data.get("heavy", "llama3.1:8b")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"InsightAgents initialized with profile '{active_profile}'. "
            f"Light: {self.light_model_name}, Heavy: {self.heavy_model_name}"
        )

        self.light_llm = LLM(
            model=f"ollama/{self.light_model_name}",
            base_url=self.ollama_base_url,
            timeout=3600.0,
        )
        self.heavy_llm = LLM(
            model=f"ollama/{self.heavy_model_name}",
            base_url=self.ollama_base_url,
            timeout=3600.0,
        )

        from custom_tools import (
            EmailClusteringTool,
            EnhancedFileReadTool,
            HierarchicalGroupingTool,
            ConversationAnalysisTool,
            HTMLMindmapGeneratorTool,
        )

        self.file_tool = EnhancedFileReadTool()
        self.cluster_tool = EmailClusteringTool()
        self.group_tool = HierarchicalGroupingTool()
        self.analysis_tool = ConversationAnalysisTool()
        self.html_mindmap_tool = HTMLMindmapGeneratorTool()

        # Agent prompt/attribute configuration
        self.agent_definitions = AgentDefinitionReader(
            os.getenv("AGENT_DEFINITION_PATH", "/app/config/agent-definition.xml")
        )

    def _build_agent(
        self,
        agent_id,
        default_role,
        default_goal,
        default_backstory,
        llm,
        tools=None,
        context=None,
    ):
        cfg = self.agent_definitions.get_agent(agent_id)
        context = context or {}

        role_tpl = cfg.get("role") or default_role
        goal_tpl = cfg.get("goal") or default_goal
        backstory_tpl = cfg.get("backstory") or default_backstory

        role = render_template(role_tpl, context)
        goal = render_template(goal_tpl, context)
        backstory = render_template(backstory_tpl, context)

        verbose_cfg = cfg.get("verbose")
        allow_cfg = cfg.get("allow_delegation")

        def _to_bool(value, default):
            if value is None:
                return default
            return str(value).strip().lower() in {"1", "true", "yes", "on"}

        verbose = _to_bool(verbose_cfg, True)
        allow_delegation = _to_bool(allow_cfg, False)

        return Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=llm,
            verbose=verbose,
            allow_delegation=allow_delegation,
            tools=tools or [],
        )

    def preprocessor_agent(self):
        return self._build_agent(
            agent_id="preprocessor",
            default_role="Email Data Preprocessor",
            default_goal="Cluster emails and save to file using tools. Do not analyze content. Output SUCCESS.",
            default_backstory=(
                "You are a data processing unit. You rely on tools to transform raw email archives into clean clusters."
            ),
            llm=self.heavy_llm,
            tools=[self.cluster_tool],
        )

    def grouper_agent(self):
        return self._build_agent(
            agent_id="grouper",
            default_role="Data Hierarchy Organizer",
            default_goal="Group cluster data into hierarchies using specified tools. Output SUCCESS.",
            default_backstory=(
                "You are a specialist in hierarchical data organization. You use tools to re-index topic clusters into Client/Project views."
            ),
            llm=self.heavy_llm,
            tools=[self.group_tool],
        )

    def analyst_agent(self, variation):
        context = {"variation": variation}
        default_role = f"Conversation Context, Sentiment & Urgency Analyst (Variation {variation})"
        default_goal = (
            "Call the conversation_analysis_tool with the conversation_file and output_file arguments to "
            f"analyze Variation {variation} topic clusters and produce the insight JSON file. Output the SUCCESS confirmation from the tool."
        )
        default_backstory = (
            "You excel at reading between the lines of corporate email threads. You detect brewing escalations, hidden blockers, and implied deadlines."
        )
        return self._build_agent(
            agent_id="analyst",
            default_role=default_role,
            default_goal=default_goal,
            default_backstory=default_backstory,
            llm=self.heavy_llm,
            tools=[self.analysis_tool],
            context=context,
        )

    def reporter_agent(self, variation):
        context = {"variation": variation}
        default_role = f"Executive Summary Reporter (Variation {variation})"
        default_goal = (
            "Synthesize executive summaries from insight JSON. Do not add conversational text."
        )
        default_backstory = (
            "You write for C-suite executives searching for critical info. You are ruthlessly concise, synthesizing rather than transcribing."
        )
        return self._build_agent(
            agent_id="reporter",
            default_role=default_role,
            default_goal=default_goal,
            default_backstory=default_backstory,
            llm=self.heavy_llm,
            tools=[],
            context=context,
        )

    def formatter_agent(self, variation):
        context = {"variation": variation}
        default_role = f"Executive Report Formatter (Variation {variation})"
        default_goal = (
            "Read insights and summaries, then return a final Markdown report. Do not add conversational text."
        )
        default_backstory = (
            "You are a precision formatter. You render structured JSON data into beautiful Markdown faithfully."
        )
        return self._build_agent(
            agent_id="formatter",
            default_role=default_role,
            default_goal=default_goal,
            default_backstory=default_backstory,
            llm=self.heavy_llm,
            tools=[self.file_tool],
            context=context,
        )

    def visualizer_agent(self, variation, visualization_logic="llm-local-large"):
        llm = self.light_llm if "mini" in visualization_logic else self.heavy_llm
        context = {"variation": variation}
        default_role = f"Interactive Mindmap Visualizer (Variation {variation})"
        default_goal = (
            "Create a self-contained D3.js HTML mindmap based on insight JSON. Use tool to read data."
        )
        default_backstory = (
            "You specialize in interactive HTML visualizations that need no external dependencies (other than D3.js)."
        )
        return self._build_agent(
            agent_id="visualizer",
            default_role=default_role,
            default_goal=default_goal,
            default_backstory=default_backstory,
            llm=llm,
            tools=[self.file_tool],
            context=context,
        )
