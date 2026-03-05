from crewai import Task
from textwrap import dedent

class InsightTasks:
    def preprocessing_task(self, agent, input_file, output_file):
        return Task(
            description=dedent(f"""\
                Task: You MUST CALL the 'semantic_email_clustering_tool' on: {input_file}.
                Required arguments: file_path="{input_file}", output_file="{output_file}"
                
                CRITICAL: Do NOT just return a SUCCESS message. You MUST execute the tool.
                The tool will perform the calculations and write the file. 
                Your only job is to trigger the tool and report the result it gives you.
            """),
            expected_output="A confirmation string starting with 'SUCCESS: ' returned directly from the tool.",
            agent=agent
        )

    def grouping_variation1_task(self, agent, clusters_file, output_file):
        return Task(
            description=dedent(f"""\
                Task: Run 'hierarchical_grouping_tool' for Variation 1.
                Inputs: 
                - clusters_file: {clusters_file}
                - output_file: {output_file}
                - variation: 1
                Expected Result: SUCCESS message.
            """),
            expected_output="A confirmation string starting with 'SUCCESS: '.",
            agent=agent
        )

    def grouping_variation2_task(self, agent, clusters_file, output_file):
        return Task(
            description=dedent(f"""\
                Task: You MUST CALL the 'hierarchical_grouping_tool' for Variation 2.
                Inputs: 
                - clusters_file: {clusters_file}
                - output_file: {output_file}
                - variation: 2
                
                CRITICAL: Do NOT simulate the result. You MUST trigger the tool.
                The tool will verify the data and write the file.
            """),
            expected_output="A confirmation string starting with 'SUCCESS: ' returned directly from the tool.",
            agent=agent
        )

    def analysis_task(self, agent, variation_file, variation_num, output_file):
        return Task(
            description=dedent(f"""\
                Task: Call 'conversation_analysis_tool' ONCE with exactly these two arguments:
                  - conversation_file: "{variation_file}"
                  - output_file: "{output_file}"
                The tool reads {variation_file}, calls the LLM per cluster internally,
                and writes {output_file} automatically. Do NOT read the file manually.
                Do NOT write JSON yourself. Just call the tool and return the SUCCESS
                confirmation it gives you.
            """),
            expected_output=f"A string starting with 'SUCCESS: ' confirming Variation {variation_num} insight file was saved to {output_file}.",
            agent=agent,
            output_file=output_file
        )

    def reporting_task(self, agent, data_context, variation_num, output_file):
        primary_key = "clients" if variation_num == 1 else "projects"
        secondary_key = "projects" if variation_num == 1 else "clients"
        hierarchy_desc = "Client Name -> Projects -> Project Name" if variation_num == 1 else "Project Name -> Clients -> Client Name"
        
        return Task(
            description=dedent(f"""\
                Task: Synthesize executive summaries for Variation {variation_num} ({hierarchy_desc}).
                
                INPUT DATA:
                {data_context}
                
                DIRECTIONS:
                1. Use ONLY the data provided above. Do NOT use any external tools.
                2. Build the JSON for Variation {variation_num}.
                
                SUMMARIZATION RULES:
                - Target: All 'summary' fields from topics where 'priorityScore' >= 3.
                - Action: Synthesize these into a SINGLE "Executive News Briefing" paragraph.
                - Style: Professional news briefing, bottom-line-first, active voice.
                - Content Goal: Consolidate redundant information and highlight only the most critical status updates into a cohesive narrative.
                - Fallback: If no topic >= 3, set summary to: "No high-priority items identified for this grouping."
                - Length: 2-5 impactful sentences.
                
                REQUIRED JSON STRUCTURE:
                The root object must contain: "date", "variation": {variation_num}, and "{primary_key}".
                Inside "{primary_key}":
                   - "NAME": {{
                       "{secondary_key}": {{
                          "SUB_NAME": {{
                             "executiveSummary": "Your paragraph here (News Briefing style)",
                             "highestPriorityScore": (Int),
                             "totalTopics": (Int count of all clusters),
                             "totalEmails": (Int count of all emails),
                             "topicsIncluded": [List of cluster titles used in summary],
                             "topicsExcluded": [List of cluster titles skipped]
                          }}
                       }}
                   }}

                CRITICAL CONSTRAINTS (LOOP PREVENTION):
                - DO NOT use any tools. Return your answer immediately.
                - DO NOT include markdown code blocks (```json).
                - DO NOT include ANY conversational text.
                - YOU MUST start your response with the character '{{'.
                - Output ONLY raw JSON matching the required structure.
            """),
            expected_output=f"A raw JSON object for Variation {variation_num}. No markdown, no conversation, no placeholders.",
            agent=agent,
            output_file=output_file
        )

    def formatting_task(self, agent, insight_file, summary_file, variation_num, output_file):
        return Task(
            description=dedent(f"""\
                Task: Create a Markdown report for Variation {variation_num}.
                1. Read {insight_file} and {summary_file} using 'read_output_json_md_tool'.
                2. Format into a professional report.
            """),
            expected_output=f'A Markdown report for Variation {variation_num}.',
            agent=agent,
            output_file=output_file
        )

    def visualization_task(self, agent, insight_file, summary_file, variation_num, output_file):
        return Task(
            description=dedent(f"""\
                Task: Generate a D3.js HTML mindmap for {insight_file}.
                1. Read {insight_file} and {summary_file} using 'read_output_json_md_tool'.
                2. Output: Raw HTML/JS code.
            """),
            expected_output=f'An HTML mindmap for Variation {variation_num}.',
            agent=agent,
            output_file=output_file
        )
