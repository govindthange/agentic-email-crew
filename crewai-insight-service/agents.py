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
        
        self.light_llm = LLM(model=f"ollama/{self.light_model_name}", base_url=self.ollama_base_url)
        self.heavy_llm = LLM(model=f"ollama/{self.heavy_model_name}", base_url=self.ollama_base_url)

    def preprocessor_agent(self):
        return Agent(
            role='Email Preprocessor & Semantic Deduplication Engine',
            goal='Read raw email archive, normalize subjects, compute embeddings, cluster similar emails into topics, and validate clusters using reasoning.',
            backstory="""You are an expert at finding the 'hidden story' buried across hundreds of emails. 
            You use semantic embeddings to cluster first, then use language reasoning to verify and label each cluster accurately.""",
            llm=self.light_llm,
            verbose=True,
            allow_delegation=False
        )

    def grouper_agent(self):
        return Agent(
            role='Conversation Thread Hierarchical Organizer',
            goal='Organize clusters into two hierarchies: Client > Project > Topic and Project > Client > Topic.',
            backstory="""You are a master librarian of corporate communications. 
            You know exactly how to file clusters into meaningful classification hierarchies for different stakeholders.""",
            llm=self.light_llm,
            verbose=True,
            allow_delegation=False
        )

    def analyst_agent(self, variation):
        return Agent(
            role=f'Conversation Context, Sentiment & Urgency Analyst (Variation {variation})',
            goal='Analyze topic clusters holistically to produce structured insights: state, next step, owner, sentiment, escalation, and blockers.',
            backstory="""You excel at reading between the lines of corporate email threads. 
            You detect brewing escalations, hidden blockers, and implied deadlines.""",
            llm=self.heavy_llm,
            verbose=True,
            allow_delegation=False
        )

    def reporter_agent(self, variation):
        return Agent(
            role=f'Executive Summary Reporter (Variation {variation})',
            goal='Synthesize a single executive summary paragraph for each grouping, focusing on high-priority items (Score >= 3).',
            backstory="""You write for C-suite executives searching for critical info. 
            You are ruthlessly concise, synthesizing rather than transcribing.""",
            llm=self.heavy_llm,
            verbose=True,
            allow_delegation=False
        )

    def formatter_agent(self, variation):
        return Agent(
            role=f'Executive Report Formatter (Variation {variation})',
            goal='Merge insights and summaries into a clean, readable Markdown report with summary statistics.',
            backstory="""You are a precision formatter. You render structured JSON data into beautiful Markdown faithfully.""",
            llm=self.light_llm,
            verbose=True,
            allow_delegation=False
        )

    def visualizer_agent(self, variation):
        return Agent(
            role=f'Interactive Mindmap Visualizer (Variation {variation})',
            goal='Generate a self-contained HTML mindmap using D3.js based on the hierarchical insights.',
            backstory="""You specialize in interactive HTML visualizations that need no external dependencies (other than D3.js).""",
            llm=self.light_llm,
            verbose=True,
            allow_delegation=False
        )
