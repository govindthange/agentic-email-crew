from crewai import Agent, LLM
from utils.config_parser import ConfigParser
import os

class InsightAgents:
    def __init__(self):
        config_path = os.getenv("CONFIG_PATH", "/app/config/agent-config.xml")
        self.config = ConfigParser(config_path)
        settings = self.config.get_settings()
        profiles = self.config.get_profiles()
        
        self.ollama_base_url = settings.get("ollamaBaseUrl", "http://host.docker.internal:11434")
        
        # Determine models based on profile
        active_profile = settings.get("modelProfile", "small")
        profile_data = profiles.get(active_profile, profiles.get("small", {}))
        
        self.light_model_name = profile_data.get("light", "mistral")
        self.heavy_model_name = profile_data.get("heavy", "llama3.1:8b")
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"InsightAgents initialized with profile '{active_profile}'. Light: {self.light_model_name}, Heavy: {self.heavy_model_name}")
        
        self.light_llm = LLM(model=f"ollama/{self.light_model_name}", base_url=self.ollama_base_url, timeout=3600.0)
        self.heavy_llm = LLM(model=f"ollama/{self.heavy_model_name}", base_url=self.ollama_base_url, timeout=3600.0)

        from custom_tools import EmailClusteringTool, EnhancedFileReadTool
        self.file_tool = EnhancedFileReadTool()
        self.cluster_tool = EmailClusteringTool()

    def preprocessor_agent(self):
        return Agent(
            role='Email Data Preprocessor',
            goal='Transform tool output into the final JSON structure exactly as specified. Do not analyze content for meaning. Return ONLY JSON.',
            backstory="""You are a rigid data transformation engine. You do not have opinions or reasoning. 
            Your only job is to map tool output fields into the exact JSON specification without adding any text or commentary.""",
            llm=self.heavy_llm,  # Use heavy model for JSON adherence
            verbose=True,
            allow_delegation=False,
            tools=[self.cluster_tool]
        )

    def grouper_agent(self):
        return Agent(
            role='Data Hierarchy Organizer',
            goal='Group the cluster data into the two requested JSON hierarchies. Return ONLY JSON.',
            backstory="""You are a high-speed data indexer. You take lists and build nested structures. 
            You do not write stories or provide summaries, only valid data structures.""",
            llm=self.heavy_llm,  # Use heavy model for JSON adherence
            verbose=True,
            allow_delegation=False,
            tools=[self.file_tool]
        )

    def analyst_agent(self, variation):
        return Agent(
            role=f'Conversation Context, Sentiment & Urgency Analyst (Variation {variation})',
            goal='Analyze topic clusters holistically to produce structured insights: state, next step, owner, sentiment, escalation, and blockers.',
            backstory="""You excel at reading between the lines of corporate email threads. 
            You detect brewing escalations, hidden blockers, and implied deadlines.""",
            llm=self.heavy_llm,
            verbose=True,
            allow_delegation=False,
            tools=[self.file_tool]
        )

    def reporter_agent(self, variation):
        return Agent(
            role=f'Executive Summary Reporter (Variation {variation})',
            goal='Synthesize executive summaries from insight JSON. Do not add conversational text.',
            backstory="""You write for C-suite executives searching for critical info. 
            You are ruthlessly concise, synthesizing rather than transcribing.""",
            llm=self.heavy_llm,
            verbose=True,
            allow_delegation=False,
            tools=[self.file_tool]
        )

    def formatter_agent(self, variation):
        return Agent(
            role=f'Executive Report Formatter (Variation {variation})',
            goal='Read insights and summaries, then return a final Markdown report. Do not add conversational text.',
            backstory="""You are a precision formatter. You render structured JSON data into beautiful Markdown faithfully.""",
            llm=self.heavy_llm,  # Use heavy model for complex formatting
            verbose=True,
            allow_delegation=False,
            tools=[self.file_tool]
        )

    def visualizer_agent(self, variation):
        return Agent(
            role=f'Interactive Mindmap Visualizer (Variation {variation})',
            goal='Create a self-contained D3.js HTML mindmap based on insight JSON. Use tool to read data.',
            backstory="""You specialize in interactive HTML visualizations that need no external dependencies (other than D3.js).""",
            llm=self.light_llm,
            verbose=True,
            allow_delegation=False,
            tools=[self.file_tool]
        )
