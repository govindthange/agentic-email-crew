import os
from crewai import Task
from textwrap import dedent
from utils.agent_definition_reader import AgentDefinitionReader, render_template


class InsightTasks:
    def __init__(self):
        self.definitions = AgentDefinitionReader(
            os.getenv("AGENT_DEFINITION_PATH", "/app/config/agent-definition.xml")
        )

    def _task_texts(self, agent_id, task_id, default_description, default_expected, context):
        cfg = self.definitions.get_task(agent_id, task_id)
        desc_tpl = cfg.get("description") or default_description
        expected_tpl = cfg.get("expected_output") or default_expected
        description = render_template(dedent(desc_tpl), context)
        expected_output = render_template(expected_tpl, context)
        return description, expected_output

    def preprocessing_task(self, agent, input_file, output_file):
        context = {"input_file": input_file, "output_file": output_file}
        default_description = """\
            Task: You MUST CALL the 'semantic_email_clustering_tool' on: ${input_file}.
            Required arguments: file_path="${input_file}", output_file="${output_file}"

            CRITICAL: Do NOT just return a SUCCESS message. You MUST execute the tool.
            The tool will perform the calculations and write the file. 
            Your only job is to trigger the tool and report the result it gives you.
        """
        default_expected = (
            "A confirmation string starting with 'SUCCESS: ' returned directly from the tool."
        )
        description, expected_output = self._task_texts(
            "preprocessor",
            "preprocessing",
            default_description,
            default_expected,
            context,
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
        )

    def grouping_variation1_task(self, agent, clusters_file, output_file):
        context = {"clusters_file": clusters_file, "output_file": output_file}
        default_description = """\
            Task: Run 'hierarchical_grouping_tool' for Variation 1.
            Inputs: 
            - clusters_file: ${clusters_file}
            - output_file: ${output_file}
            - variation: 1
            Expected Result: SUCCESS message.
        """
        default_expected = "A confirmation string starting with 'SUCCESS: '."
        description, expected_output = self._task_texts(
            "grouper",
            "grouping_variation1",
            default_description,
            default_expected,
            context,
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
        )

    def grouping_variation2_task(self, agent, clusters_file, output_file):
        context = {"clusters_file": clusters_file, "output_file": output_file}
        default_description = """\
            Task: You MUST CALL the 'hierarchical_grouping_tool' for Variation 2.
            Inputs: 
            - clusters_file: ${clusters_file}
            - output_file: ${output_file}
            - variation: 2

            CRITICAL: Do NOT simulate the result. You MUST trigger the tool.
            The tool will verify the data and write the file.
        """
        default_expected = (
            "A confirmation string starting with 'SUCCESS: ' returned directly from the tool."
        )
        description, expected_output = self._task_texts(
            "grouper",
            "grouping_variation2",
            default_description,
            default_expected,
            context,
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
        )

    def analysis_task(self, agent, variation_file, variation_num, output_file):
        context = {
            "variation_file": variation_file,
            "variation_num": variation_num,
            "output_file": output_file,
        }
        default_description = """\
            Task: Call 'conversation_analysis_tool' ONCE with exactly these two arguments:
              - conversation_file: "${variation_file}"
              - output_file: "${output_file}"
            The tool reads ${variation_file}, calls the LLM per cluster internally,
            and writes ${output_file} automatically. Do NOT read the file manually.
            Do NOT write JSON yourself. Just call the tool and return the SUCCESS
            confirmation it gives you.
        """
        default_expected = (
            "A string starting with 'SUCCESS: ' confirming Variation "
            "${variation_num} insight file was saved to ${output_file}."
        )
        description, expected_output = self._task_texts(
            "analyst",
            "analysis",
            default_description,
            default_expected,
            context,
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            output_file=output_file,
        )

    def reporting_task(self, agent, data_context, variation_num, output_file):
        primary_key = "clients" if variation_num == 1 else "projects"
        secondary_key = "projects" if variation_num == 1 else "clients"
        hierarchy_desc = (
            "Client Name -> Projects -> Project Name"
            if variation_num == 1
            else "Project Name -> Clients -> Client Name"
        )
        context = {
            "data_context": data_context,
            "variation_num": variation_num,
            "primary_key": primary_key,
            "secondary_key": secondary_key,
            "hierarchy_desc": hierarchy_desc,
        }
        default_description = """\
            Task: Synthesize executive summaries for Variation ${variation_num} (${hierarchy_desc}).
            
            INPUT DATA:
            ${data_context}
            
            DIRECTIONS:
            1. Use ONLY the data provided above. Do NOT use any external tools.
            2. Build the JSON for Variation ${variation_num}.
            
            SUMMARIZATION RULES:
            - Target: All 'summary' fields from topics where 'priorityScore' >= 3.
            - Action: Synthesize these into a SINGLE "Executive News Briefing" paragraph.
            - Style: Professional news briefing, bottom-line-first, active voice.
            - Content Goal: Consolidate redundant information and highlight only the most critical status updates into a cohesive narrative.
            - Fallback: If no topic >= 3, set summary to: "No high-priority items identified for this grouping."
            - Length: 2-5 impactful sentences.
            
            REQUIRED JSON STRUCTURE:
            The root object must contain: "date", "variation": ${variation_num}, and "${primary_key}".
            Inside "${primary_key}":
               - "NAME": {
                   "${secondary_key}": {
                      "SUB_NAME": {
                         "executiveSummary": "Your paragraph here (News Briefing style)",
                         "highestPriorityScore": (Int),
                         "totalTopics": (Int count of all clusters),
                         "totalEmails": (Int count of all emails),
                         "topicsIncluded": [List of cluster titles used in summary],
                         "topicsExcluded": [List of cluster titles skipped]
                      }
                   }
               }
            
            CRITICAL CONSTRAINTS (LOOP PREVENTION):
            - DO NOT use any tools. Return your answer immediately.
            - DO NOT include markdown code blocks (```json).
            - DO NOT include ANY conversational text.
            - YOU MUST start your response with the character '{'.
            - Output ONLY raw JSON matching the required structure.
        """
        default_expected = (
            "A raw JSON object for Variation ${variation_num}. "
            "No markdown, no conversation, no placeholders."
        )
        description, expected_output = self._task_texts(
            "reporter",
            "reporting",
            default_description,
            default_expected,
            context,
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            output_file=output_file,
        )

    def formatting_task(self, agent, insight_file, summary_file, variation_num, output_file):
        primary_key = "clients" if variation_num == 1 else "projects"
        secondary_key = "projects" if variation_num == 1 else "clients"
        hierarchy_desc = (
            "Client -> Project -> Topic"
            if variation_num == 1
            else "Project -> Client -> Topic"
        )
        context = {
            "insight_file": insight_file,
            "summary_file": summary_file,
            "variation_num": variation_num,
            "hierarchy_desc": hierarchy_desc,
            "primary_singular": primary_key.rstrip("s"),
            "secondary_singular": secondary_key.rstrip("s"),
            "primary_capitalized": primary_key.rstrip("s").capitalize(),
            "secondary_capitalized": secondary_key.rstrip("s").capitalize(),
        }
        default_description = """\
            Task: Create a Human-Readable Markdown Report for Variation ${variation_num} (${hierarchy_desc}).
            
            STEPS:
            1. Read ${insight_file} and ${summary_file} using ONLY 'read_output_json_md_tool'.
            2. Merge the data into a single coherent report.
            
            REPORT STRUCTURE:
            - Title: Executive Insight Report - Variation ${variation_num} (${hierarchy_desc})
            - For each ${primary_singular}:
                - Header level 1: ${primary_capitalized} Name
                - For each ${secondary_singular}:
                    - Header level 2: ${secondary_capitalized} Name
                    - Blockquote: Include the "executiveSummary" from the summary JSON here.
                    - For each Topic in this group:
                        - Header level 3: Topic Title
                        - Section: Topic Summary, Owner, State, Next Action, Priority.
            
            CRITICAL CONSTRAINTS:
            - DO NOT use any tools other than 'read_output_json_md_tool'.
            - DO NOT use any tools like 'generate_report'. You must format it yourself.
            - DO NOT include conversational filler like "Here is the report".
            - Return ONLY the raw Markdown content.
        """
        default_expected = (
            "A complete Markdown report for Variation ${variation_num} "
            "following the prescribed structure."
        )
        description, expected_output = self._task_texts(
            "formatter",
            "formatting",
            default_description,
            default_expected,
            context,
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            output_file=output_file,
        )

    def visualization_task(
        self,
        agent,
        insight_file,
        summary_file,
        variation_num,
        output_file,
        visualization_logic="llm-local-large",
    ):
        context = {
            "insight_file": insight_file,
            "summary_file": summary_file,
            "variation_num": variation_num,
        }
        default_description = """\
            Task: Generate a Self-Contained D3.js HTML Mindmap for Variation ${variation_num}.
            
            STEPS:
            1. Read ${insight_file} and ${summary_file} using ONLY 'read_output_json_md_tool'.
            2. Transform the hierarchical data into a single HTML file.
            
            VISUALIZATION REQUIREMENTS:
            - Use vanilla D3.js (loaded via CDN, e.g., https://d3js.org/d3.v7.min.js).
            - Root Node: "Daily Insights — Variation ${variation_num}"
            - Hierarchy: Follow the structure in ${insight_file}.
            - Interactivity: Nodes must be click-to-expand/collapse.
            - Tooltips: Hovering a topic node shows its summary and priority.
            - Color coding: Color nodes based on 'priorityScore' (1-5).
            
            CRITICAL CONSTRAINTS:
            - The 'read_output_json_md_tool' is ONLY for reading input data. It CANNOT generate HTML.
            - DO NOT attempt to call tools like 'generate_mindmap' or 'create_d3_mindmap'. YOU must write the full HTML code yourself.
            - Return ONLY the raw HTML/JS code. Start with "<!DOCTYPE html>".
            - DO NOT wrap the output in markdown backticks (```html).
            - Use a high-quality D3.js tree or cluster layout with the requested interactivity.
        """
        default_expected = (
            "A single-file HTML mindmap for Variation ${variation_num} with internal JS/CSS."
        )
        description, expected_output = self._task_texts(
            "visualizer",
            "visualization",
            default_description,
            default_expected,
            context,
        )
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            output_file=output_file,
        )
