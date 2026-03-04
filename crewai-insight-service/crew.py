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

        # 2. Grouping — Call HierarchicalGroupingTool DIRECTLY (no LLM wrapper).
        # The tool is pure deterministic Python: calling it via a CrewAI agent lets
        # the LLM hallucinate SUCCESS without ever invoking the tool (confirmed in logs).
        # Direct Python call is identical to the EmailClusteringTool pattern for Agent 1.
        from custom_tools import HierarchicalGroupingTool
        group_tool = HierarchicalGroupingTool()

        abs_v1_file = os.path.join(abs_data_dir, f"conversation-variation1-{date_str}.json")
        abs_v2_file = os.path.join(abs_data_dir, f"conversation-variation2-{date_str}.json")

        logger.info(f"Grouping: calling HierarchicalGroupingTool directly for Variation 1 → {abs_v1_file}")
        result_v1 = group_tool._run(
            clusters_file=abs_clusters_file,
            output_file=abs_v1_file,
            variation=1
        )
        logger.info(f"Grouping V1 result: {result_v1}")
        if not result_v1.startswith("SUCCESS"):
            logger.error(f"Grouping Variation 1 failed: {result_v1}. Halting pipeline.")
            return

        logger.info(f"Grouping: calling HierarchicalGroupingTool directly for Variation 2 → {abs_v2_file}")
        result_v2 = group_tool._run(
            clusters_file=abs_clusters_file,
            output_file=abs_v2_file,
            variation=2
        )
        logger.info(f"Grouping V2 result: {result_v2}")
        if not result_v2.startswith("SUCCESS"):
            logger.error(f"Grouping Variation 2 failed: {result_v2}. Halting pipeline.")
            return

        if not os.path.exists(abs_v1_file):
            logger.error(f"Variation 1 conversation file not found at {abs_v1_file} after grouping. Halting.")
            return
        if not os.path.exists(abs_v2_file):
            logger.error(f"Variation 2 conversation file not found at {abs_v2_file} after grouping. Halting.")
            return

        # 3. Analysis — run Variation 1 then Variation 2 sequentially using tool.
        from custom_tools import ConversationAnalysisTool
        analysis_tool = ConversationAnalysisTool()
        variation_insights = {}

        for var_num, var_file in [(1, abs_v1_file), (2, abs_v2_file)]:
            insight_file = os.path.join(abs_data_dir, f"insight-variation{var_num}-{date_str}.json")
            logger.info(f"Agent 3{'a' if var_num == 1 else 'b'}: analysing {var_file} → {insight_file}")
            try:
                result = analysis_tool._run(
                    conversation_file=var_file,
                    output_file=insight_file
                )
                logger.info(f"Variation {var_num} analysis result: {result}")
                if not result.startswith("SUCCESS"):
                    logger.error(f"Variation {var_num} analysis failed: {result}. Halting.")
                    return
                variation_insights[var_num] = insight_file
            except Exception as exc:
                logger.error(f"Variation {var_num} analysis raised exception: {exc}", exc_info=True)
                return

        logger.info("Both variation analyses completed. Proceeding to Reporting (Agent 4).")

        # 4. Reporting (Agent 4a and 4b) — Must finish before Agents 5/6 start.
        summary_files = {}
        execution_mode = self.agents.config.get_setting("agentExecutionMode", "sequential")
        logger.info(f"Agent Reporting Execution Mode: {execution_mode}")
        
        def run_reporter(v_num, ins_file):
            logger.info(f"Starting Reporter Agent 4{'a' if v_num == 1 else 'b'} for Variation {v_num}")
            agent = self.agents.reporter_agent(v_num)
            # Relative path for CrewAI output to avoid path issues
            rel_summary = os.path.join(data_dir, f"summary-variation{v_num}-{date_str}.json")
            task = self.tasks.reporting_task(agent, ins_file, v_num, rel_summary)
            crew = Crew(agents=[agent], tasks=[task], verbose=True, embedder=self.embedder_config)
            crew.kickoff()
            summary_files[v_num] = os.path.join(abs_data_dir, f"summary-variation{v_num}-{date_str}.json")
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
            # Sequential (default)
            for v_num in [1, 2]:
                run_reporter(v_num, variation_insights[v_num])
            
        logger.info("All Reporting (Agent 4) completed. Starting Formatting and Visualization (Agents 5/6).")

        # 5. Formatting (Agent 5) and Visualization (Agent 6) — Parallel execution.
        final_threads = []
        
        def run_formatter(v_num, ins_file, sum_file):
            logger.info(f"Starting Formatter Agent 5{'a' if v_num == 1 else 'b'} for Variation {v_num}")
            agent = self.agents.formatter_agent(v_num)
            rel_report = os.path.join(data_dir, f"report-variation{v_num}-{date_str}.md")
            abs_sum_file = os.path.join(abs_data_dir, os.path.basename(sum_file))
            task = self.tasks.formatting_task(agent, ins_file, abs_sum_file, v_num, rel_report)
            Crew(agents=[agent], tasks=[task], verbose=True, embedder=self.embedder_config).kickoff()
            logger.info(f"Formatter Agent 5{'a' if v_num == 1 else 'b'} finished.")

        def run_visualizer(v_num, ins_file, sum_file):
            logger.info(f"Starting Visualizer Agent 6{'a' if v_num == 1 else 'b'} for Variation {v_num}")
            agent = self.agents.visualizer_agent(v_num)
            rel_mindmap = os.path.join(data_dir, f"mindmap-variation{v_num}-{date_str}.html")
            abs_sum_file = os.path.join(abs_data_dir, os.path.basename(sum_file))
            task = self.tasks.visualization_task(agent, ins_file, abs_sum_file, v_num, rel_mindmap)
            Crew(agents=[agent], tasks=[task], verbose=True, embedder=self.embedder_config).kickoff()
            logger.info(f"Visualizer Agent 6{'a' if v_num == 1 else 'b'} finished.")

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
