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

        from custom_tools import EmailClusteringTool, EnhancedFileReadTool, HierarchicalGroupingTool, ConversationAnalysisTool, HTMLMindmapGeneratorTool
        self.file_tool = EnhancedFileReadTool()
        self.cluster_tool = EmailClusteringTool()
        self.group_tool = HierarchicalGroupingTool()
        self.analysis_tool = ConversationAnalysisTool()
        self.html_mindmap_tool = HTMLMindmapGeneratorTool()

    def preprocessor_agent(self):
        return Agent(
            role='Email Data Preprocessor',
            goal='Cluster emails and save to file using tools. Do not analyze content. Output SUCCESS.',
            backstory="""You are a data processing unit. You rely on tools to transform raw email archives into clean clusters.""",
            llm=self.heavy_llm,
            verbose=True,
            allow_delegation=False,
            tools=[self.cluster_tool]
        )

    def grouper_agent(self):
        return Agent(
            role='Data Hierarchy Organizer',
            goal='Group cluster data into hierarchies using specified tools. Output SUCCESS.',
            backstory="""You are a specialist in hierarchical data organization. You use tools to re-index topic clusters into Client/Project views.""",
            llm=self.heavy_llm,
            verbose=True,
            allow_delegation=False,
            tools=[self.group_tool]
        )

    def analyst_agent(self, variation):
        return Agent(
            role=f'Conversation Context, Sentiment & Urgency Analyst (Variation {variation})',
            goal=(
                f'Call the conversation_analysis_tool with the conversation_file and output_file '
                f'arguments to analyze Variation {variation} topic clusters and produce the insight JSON file. '
                f'Output the SUCCESS confirmation from the tool.'
            ),
            backstory="""You excel at reading between the lines of corporate email threads. 
            You detect brewing escalations, hidden blockers, and implied deadlines.""",
            llm=self.heavy_llm,
            verbose=True,
            allow_delegation=False,
            tools=[self.analysis_tool]
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
            tools=[]
        )

    def formatter_agent(self, variation):
        return Agent(
            role=f'Executive Report Formatter (Variation {variation})',
            goal='Read insights and summaries, then return a final Markdown report. Do not add conversational text.',
            backstory="""You are a precision formatter. You render structured JSON data into beautiful Markdown faithfully.""",
            llm=self.heavy_llm,
            verbose=True,
            allow_delegation=False,
            tools=[self.file_tool]
        )

    def visualizer_agent(self, variation, visualization_logic="llm-local-large"):
        llm = self.light_llm if "mini" in visualization_logic else self.heavy_llm
        return Agent(
            role=f'Interactive Mindmap Visualizer (Variation {variation})',
            goal='Create a self-contained D3.js HTML mindmap based on insight JSON. Use tool to read data.',
            backstory="""You specialize in interactive HTML visualizations that need no external dependencies (other than D3.js).""",
            llm=llm,
            verbose=True,
            allow_delegation=False,
            tools=[self.file_tool]
        )
