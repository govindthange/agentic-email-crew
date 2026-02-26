from crewai import Crew, Process
from agents import InsightAgents
from tasks import InsightTasks
import os
import re
import json
import logging

logger = logging.getLogger(__name__)

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
        # Extract date from archive filename robustly
        # Supports: archive-YYYYMMDD.json, test-YYYYMMDD.json, etc.
        basename = os.path.basename(archive_file)
        date_match = re.search(r'(\d{8})', basename)
        if not date_match:
            logger.error(f"Cannot extract date from archive filename: {basename}")
            return
        date_str = date_match.group(1)
        logger.info(f"Processing archive for date: {date_str}, file: {archive_file}")

        # CrewAI 1.9.3 natively converts absolute paths to relative by stripping the leading slash.
        # To avoid saving to /app/app/data/..., we use a relative path for output_file.
        data_dir = "data"

        # Relative paths for CrewAI output_file parameter
        clusters_file = os.path.join(data_dir, f"clusters-{date_str}.json")
        group_v1_file = os.path.join(data_dir, f"conversation-variation1-{date_str}.json")
        group_v2_file = os.path.join(data_dir, f"conversation-variation2-{date_str}.json")

        # Absolute paths for task descriptions (so agents/tools can find the files)
        abs_data_dir = os.getenv("DATA_DIR", "/app/data")
        abs_clusters_file = os.path.join(abs_data_dir, f"clusters-{date_str}.json")

        # 1. Preprocessing
        pre_agent = self.agents.preprocessor_agent()
        pre_task = self.tasks.preprocessing_task(pre_agent, archive_file, clusters_file)
        
        pre_crew = Crew(
            agents=[pre_agent],
            tasks=[pre_task],
            process=Process.sequential,
            embedder=self.embedder_config
        )
        clusters = pre_crew.kickoff()
        
        # Verify clusters file was created before proceeding
        if not os.path.exists(abs_clusters_file):
            # Also check relative path (in case CWD is /app)
            if os.path.exists(clusters_file):
                abs_clusters_file = os.path.abspath(clusters_file)
            else:
                logger.error(f"Clusters file not created at {abs_clusters_file} or {clusters_file}. Halting pipeline.")
                return
        
        logger.info(f"Clusters file created at: {abs_clusters_file}")

        # 2. Grouping — Run Variation 1 and Variation 2 as separate tasks for better reliability
        group_agent = self.agents.grouper_agent()
        group_v1_task = self.tasks.grouping_variation1_task(group_agent, abs_clusters_file, group_v1_file)
        group_v2_task = self.tasks.grouping_variation2_task(group_agent, abs_clusters_file, group_v2_file)
        
        group_crew = Crew(
            agents=[group_agent],
            tasks=[group_v1_task, group_v2_task],
            process=Process.sequential,
            embedder=self.embedder_config
        )
        group_crew.kickoff()
        
        # Variation 1 Branch
        self._run_variation(1, group_v1_file, date_str, data_dir, abs_data_dir)
        
        # Variation 2 Branch
        self._run_variation(2, group_v2_file, date_str, data_dir, abs_data_dir)

    def _run_variation(self, var_num, var_file, date_str, data_dir, abs_data_dir):
        analyst = self.agents.analyst_agent(var_num)
        reporter = self.agents.reporter_agent(var_num)
        formatter = self.agents.formatter_agent(var_num)
        visualizer = self.agents.visualizer_agent(var_num)
        
        # Relative paths for CrewAI output_file
        insight_file = os.path.join(data_dir, f"insight-variation{var_num}-{date_str}.json")
        summary_file = os.path.join(data_dir, f"summary-variation{var_num}-{date_str}.json")
        report_file = os.path.join(data_dir, f"report-variation{var_num}-{date_str}.md")
        mindmap_file = os.path.join(data_dir, f"mindmap-variation{var_num}-{date_str}.html")

        # Absolute paths for task descriptions  
        abs_var_file = os.path.join(abs_data_dir, os.path.basename(var_file))
        abs_insight_file = os.path.join(abs_data_dir, f"insight-variation{var_num}-{date_str}.json")
        abs_summary_file = os.path.join(abs_data_dir, f"summary-variation{var_num}-{date_str}.json")

        # Each variation runs as its own crew with sequential tasks
        var_crew = Crew(
            agents=[analyst, reporter, formatter, visualizer],
            tasks=[
                self.tasks.analysis_task(analyst, abs_var_file, var_num, insight_file),
                self.tasks.reporting_task(reporter, abs_insight_file, var_num, summary_file),
                self.tasks.formatting_task(formatter, abs_insight_file, abs_summary_file, var_num, report_file),
                self.tasks.visualization_task(visualizer, abs_insight_file, var_num, mindmap_file)
            ],
            process=Process.sequential,
            embedder=self.embedder_config
        )
        return var_crew.kickoff()
