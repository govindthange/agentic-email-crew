from crewai import Crew, Process
from agents import InsightAgents
from tasks import InsightTasks
import os
import re
import json
import logging
import threading

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
        
        if os.path.exists(abs_clusters_file):
            logger.info(f"Skipping Preprocessing: {abs_clusters_file} already exists.")
        else:
            pre_crew = Crew(
                agents=[pre_agent],
                tasks=[pre_task],
                process=Process.sequential,
                embedder=self.embedder_config
            )
            pre_crew.kickoff()
        
        # Ensure we have the clusters file (either pre-existing or just created)
        if not os.path.exists(abs_clusters_file):
            # Check relative path as fallback
            if os.path.exists(clusters_file):
                abs_clusters_file = os.path.abspath(clusters_file)
            else:
                logger.error(f"Clusters file missing at {abs_clusters_file}. Halting pipeline.")
                return
        
        logger.info(f"Clusters file ready: {abs_clusters_file}")

        # 2. Grouping
        from custom_tools import HierarchicalGroupingTool
        group_tool = HierarchicalGroupingTool()

        abs_v1_file = os.path.join(abs_data_dir, f"conversation-variation1-{date_str}.json")
        abs_v2_file = os.path.join(abs_data_dir, f"conversation-variation2-{date_str}.json")

        for v_num, v_file in [(1, abs_v1_file), (2, abs_v2_file)]:
            if os.path.exists(v_file):
                logger.info(f"Skipping Grouping V{v_num}: {v_file} already exists.")
            else:
                logger.info(f"Grouping: calling HierarchicalGroupingTool for Variation {v_num} → {v_file}")
                result = group_tool._run(clusters_file=abs_clusters_file, output_file=v_file, variation=v_num)
                if not result.startswith("SUCCESS"):
                    logger.error(f"Grouping Variation {v_num} failed: {result}. Halting.")
                    return

        # 3. Analysis
        from custom_tools import ConversationAnalysisTool
        analysis_tool = ConversationAnalysisTool()
        variation_insights = {}

        for var_num, var_file in [(1, abs_v1_file), (2, abs_v2_file)]:
            insight_file = os.path.join(abs_data_dir, f"insight-variation{var_num}-{date_str}.json")
            variation_insights[var_num] = insight_file
            
            if os.path.exists(insight_file):
                logger.info(f"Skipping Analysis V{var_num}: {insight_file} already exists.")
            else:
                logger.info(f"Agent 3{'a' if var_num == 1 else 'b'}: analysing {var_file} → {insight_file}")
                try:
                    result = analysis_tool._run(conversation_file=var_file, output_file=insight_file)
                    if not result.startswith("SUCCESS"):
                        logger.error(f"Variation {var_num} analysis failed: {result}. Halting.")
                        return
                except Exception as exc:
                    logger.error(f"Variation {var_num} analysis raised exception: {exc}", exc_info=True)
                    return

        # 4. Reporting (Agent 4a and 4b)
        summary_files = {}
        execution_mode = self.agents.config.get_setting("agentExecutionMode", "sequential")
        
        def run_reporter(v_num, ins_file):
            abs_summary = os.path.join(abs_data_dir, f"summary-variation{v_num}-{date_str}.json")
            summary_files[v_num] = abs_summary
            
            if os.path.exists(abs_summary):
                logger.info(f"Skipping Reporting V{v_num}: {abs_summary} already exists.")
                return

            logger.info(f"Starting Reporter Agent 4{'a' if v_num == 1 else 'b'} for Variation {v_num}")
            
            # Read the insight data directly to pass as context
            try:
                with open(ins_file, 'r') as f:
                    data_context = f.read()
            except Exception as e:
                logger.error(f"Failed to read insight file {ins_file}: {e}")
                return

            agent = self.agents.reporter_agent(v_num)
            rel_summary = os.path.join(data_dir, f"summary-variation{v_num}-{date_str}.json")
            task = self.tasks.reporting_task(agent, data_context, v_num, rel_summary)
            Crew(agents=[agent], tasks=[task], verbose=True, embedder=self.embedder_config).kickoff()
            logger.info(f"Reporter Agent 4{'a' if v_num == 1 else 'b'} finished.")

        if execution_mode == "parallel":
            report_threads = []
            for v_num in [1, 2]:
                t = threading.Thread(target=run_reporter, args=(v_num, variation_insights[v_num]))
                t.start()
                report_threads.append(t)
            for t in report_threads:
                t.join()
        else:
            for v_num in [1, 2]:
                run_reporter(v_num, variation_insights[v_num])
            
        logger.info("Reporting phase complete. Starting Formatting and Visualization.")

        # 5. Formatting (Agent 5) and Visualization (Agent 6)
        final_threads = []
        
        def run_formatter(v_num, ins_file, sum_file):
            abs_report = os.path.join(abs_data_dir, f"report-variation{v_num}-{date_str}.md")
            if os.path.exists(abs_report):
                logger.info(f"Skipping Formatter V{v_num}: {abs_report} already exists.")
                return

            logger.info(f"Starting Formatter Agent 5{'a' if v_num == 1 else 'b'} for Variation {v_num}")
            agent = self.agents.formatter_agent(v_num)
            rel_report = os.path.join(data_dir, f"report-variation{v_num}-{date_str}.md")
            task = self.tasks.formatting_task(agent, ins_file, sum_file, v_num, rel_report)
            Crew(agents=[agent], tasks=[task], verbose=True, embedder=self.embedder_config).kickoff()

        def run_visualizer(v_num, ins_file, sum_file):
            abs_mindmap = os.path.join(abs_data_dir, f"mindmap-variation{v_num}-{date_str}.html")
            if os.path.exists(abs_mindmap):
                logger.info(f"Skipping Visualizer V{v_num}: {abs_mindmap} already exists.")
                return

            logger.info(f"Starting Visualizer Agent 6{'a' if v_num == 1 else 'b'} for Variation {v_num}")
            agent = self.agents.visualizer_agent(v_num)
            rel_mindmap = os.path.join(data_dir, f"mindmap-variation{v_num}-{date_str}.html")
            task = self.tasks.visualization_task(agent, ins_file, sum_file, v_num, rel_mindmap)
            Crew(agents=[agent], tasks=[task], verbose=True, embedder=self.embedder_config).kickoff()

        for v_num in [1, 2]:
            ins_file = variation_insights[v_num]
            sum_file = summary_files[v_num]
            
            t5 = threading.Thread(target=run_formatter, args=(v_num, ins_file, sum_file))
            t5.start()
            final_threads.append(t5)
            
            t6 = threading.Thread(target=run_visualizer, args=(v_num, ins_file, sum_file))
            t6.start()
            final_threads.append(t6)
            
        for t in final_threads:
            t.join()
            
        logger.info(f"Pipeline completed successfully for date {date_str}.")
