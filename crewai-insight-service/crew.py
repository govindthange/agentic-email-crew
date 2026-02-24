from crewai import Crew, Process
from agents import InsightAgents
from tasks import InsightTasks
import os
import json

class EmailInsightCrew:
    def __init__(self):
        self.agents = InsightAgents()
        self.tasks = InsightTasks()
        self.embedder_config = {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text",
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
            }
        }

    def run(self, archive_file):
        # 1. Preprocessing
        pre_agent = self.agents.preprocessor_agent()
        pre_task = self.tasks.preprocessing_task(pre_agent, archive_file)
        
        pre_crew = Crew(
            agents=[pre_agent],
            tasks=[pre_task],
            process=Process.sequential,
            embedder=self.embedder_config
        )
        clusters = pre_crew.kickoff()
        
        # 2. Grouping
        group_agent = self.agents.grouper_agent()
        group_task = self.tasks.grouping_task(group_agent)
        
        group_crew = Crew(
            agents=[group_agent],
            tasks=[group_task],
            process=Process.sequential,
            embedder=self.embedder_config
        )
        groups = group_crew.kickoff()
        
        # Variation 1 Branch
        self._run_variation(1, "conversation-variation1.json")
        
        # Variation 2 Branch
        self._run_variation(2, "conversation-variation2.json")

    def _run_variation(self, var_num, var_file):
        analyst = self.agents.analyst_agent(var_num)
        reporter = self.agents.reporter_agent(var_num)
        formatter = self.agents.formatter_agent(var_num)
        visualizer = self.agents.visualizer_agent(var_num)
        
        # Implementation of variation-specific tasks
        # Each variation would be its own crew or a single crew with parallel tasks
        var_crew = Crew(
            agents=[analyst, reporter, formatter, visualizer],
            tasks=[
                self.tasks.analysis_task(analyst, var_file, var_num),
                self.tasks.reporting_task(reporter, f"insight-v{var_num}.json", var_num),
                self.tasks.formatting_task(formatter, f"insight-v{var_num}.json", f"summary-v{var_num}.json", var_num),
                self.tasks.visualization_task(visualizer, f"insight-v{var_num}.json", var_num)
            ],
            process=Process.sequential,
            embedder=self.embedder_config
        )
        return var_crew.kickoff()
