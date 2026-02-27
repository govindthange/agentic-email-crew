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
        return Task(
            description=dedent(f"""\
                Task: Write executive summaries for {insight_file}.
                1. Read file using 'read_output_json_md_tool'.
                2. Output: ONLY raw JSON. No markdown blocks.
            """),
            expected_output=f'A JSON object for Variation {variation_num} containing executive summaries.',
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

    def visualization_task(self, agent, insight_file, variation_num, output_file):
        return Task(
            description=dedent(f"""\
                Task: Generate a D3.js HTML mindmap for {insight_file}.
                1. Read {insight_file} using 'read_output_json_md_tool'.
                2. Output: Raw HTML/JS code.
            """),
            expected_output=f'An HTML mindmap for Variation {variation_num}.',
            agent=agent,
            output_file=output_file
        )
