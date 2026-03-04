from crewai import Task
from textwrap import dedent

class InsightTasks:
    def preprocessing_task(self, agent, input_file, output_file):
        return Task(
            description=dedent(f"""\
                Task: Run 'semantic_email_clustering_tool' on: {input_file} 
                and save the output directly to {output_file}.
                Required arguments: file_path="{input_file}", output_file="{output_file}"
                Expected Result: A confirmation string starting with 'SUCCESS: '.
            """),
            expected_output="A confirmation string starting with 'SUCCESS: '.",
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
                Task: Run 'hierarchical_grouping_tool' for Variation 2.
                Inputs: 
                - clusters_file: {clusters_file}
                - output_file: {output_file}
                - variation: 2
                Expected Result: SUCCESS message.
            """),
            expected_output="A confirmation string starting with 'SUCCESS: '.",
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

    def reporting_task(self, agent, insight_file, variation_num, output_file):
        grouping_v1 = "Client > Project"
        grouping_v2 = "Project > Client"
        active_grouping = grouping_v1 if variation_num == 1 else grouping_v2
        
        target_structure = dedent(f"""
            {{
              "date": "YYYYMMDD",
              "variation": {variation_num},
              "grouping": "{active_grouping} > Executive Summary",
              "{'clients' if variation_num == 1 else 'projects'}": {{
                "NAME": {{
                  "{'projects' if variation_num == 1 else 'clients'}": {{
                    "SUB_NAME": {{
                      "{'client' if variation_num == 1 else 'project'}": "NAME",
                      "{'project' if variation_num == 1 else 'client'}": "SUB_NAME",
                      "executiveSummary": "3-6 sentences covering critical issues, blockers, and actions.",
                      "highestPriorityScore": 5,
                      "totalTopics": 10,
                      "totalEmails": 50,
                      "topicsIncluded": ["cluster-001", "cluster-002"],
                      "topicsExcluded": ["cluster-005"]
                    }}
                  }}
                }}
              }}
            }}
        """)

        return Task(
            description=dedent(f"""\
                Task: Read {insight_file} and synthesize executive summaries for Variation {variation_num}.
                
                Step 1: Use 'read_output_json_md_tool' to read EVERYTHING from: {insight_file}
                Step 2: Traverse the hierarchy ({active_grouping}). 
                Step 3: For each sub-group (the leaf node containing 'topics'):
                   - Filter: Only topics with priorityScore >= 3 are used for the summary.
                   - Topics with priorityScore <= 2 are excluded from the summary but tracked in 'topicsExcluded'.
                   - If NO topics meet the threshold (>=3), the summary MUST be: "No high-priority items identified under this grouping for YYYYMMDD."
                Step 4: Synthesize a single executive summary paragraph for the sub-group:
                   - Length: 3-6 sentences. 
                   - Style: Plain English, newsfeed highlight style, NO bullet points.
                   - Content: Most critical issue, current state, active blockers/escalations (with owner names), financial items (invoices/POs) status, and recommended action.
                
                Step 5 (CRITICAL): Plan the output.
                   - First, think step-by-step about the keys needed for the {active_grouping} hierarchy.
                   - Ensure Variation {variation_num} structure is followed: {'Client > Project' if variation_num == 1 else 'Project > Client'}.

                Final Output Requirement:
                - Output ONLY the raw JSON matching this structure:
                {target_structure}
                - 'totalTopics' and 'totalEmails' must be the aggregate sums from the original topics list (including excluded ones).
                - 'highestPriorityScore' is the max score found in that sub-group.
                - Do NOT include markdown code blocks (```json) or conversational text. Return ONLY the JSON object.
            """),
            expected_output=f'A JSON object for Variation {variation_num} containing executive summaries mapped to the hierarchy.',
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
