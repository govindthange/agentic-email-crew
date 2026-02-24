from crewai import Task
from textwrap import dedent

class InsightTasks:
    def preprocessing_task(self, agent, input_file):
        return Task(
            description=dedent(f"""
                1. Read the raw email archive from {input_file}.
                2. Normalize subject lines (strip Re:, Fwd:, etc.).
                3. Cluster emails into topic groups using semantic similarity (threshold 0.82).
                4. For each cluster, validate it using reasoning, assign a descriptive topicTitle, and identify client/project.
                5. Exclude noise (alerts, invites) but keep for audit.
                6. Output a structured JSON of clusters.
            """),
            expected_output='A JSON object containing total emails read, total clusters, noise emails, and a list of clusters with topicTitle, client, project, and emails.',
            agent=agent
        )

    def grouping_task(self, agent):
        return Task(
            description=dedent("""
                1. Read the clusters JSON and agent-config.xml.
                2. Create Variation 1: Client > Project > Topic.
                3. Create Variation 2: Project > Client > Topic.
                4. Ensure multi-value duplication (one cluster appearing in multiple branches).
            """),
            expected_output='Two structured JSON objects, one for each variation hierarchy.',
            agent=agent
        )

    def analysis_task(self, agent, variation_file, variation_num):
        return Task(
            description=dedent(f"""
                1. Read {variation_file}.
                2. For each Topic cluster, analyze all emails chronologically.
                3. Determine Current State, Next Step, Owner, Sentiment, Escalation, and Blockers.
                4. Assign Priority Score (1-5).
                5. Output Variation {variation_num} insight JSON replacing emails array with insight objects.
            """),
            expected_output=f'A JSON object for Variation {variation_num} preserving hierarchy with detailed insight objects at topic level.',
            agent=agent
        )

    def reporting_task(self, agent, insight_file, variation_num):
        return Task(
            description=dedent(f"""
                1. Read insights from {insight_file}.
                2. For each group, synthesize a single executive summary paragraph (3-6 sentences).
                3. Only include items with priorityScore >= 3.
                4. Output Variation {variation_num} summary JSON.
            """),
            expected_output=f'A JSON object for Variation {variation_num} containing executive summaries for each grouping.',
            agent=agent
        )

    def formatting_task(self, agent, insight_file, summary_file, variation_num):
        return Task(
            description=dedent(f"""
                1. Merge {insight_file} and {summary_file}.
                2. Format as a comprehensive Markdown report.
                3. Include Summary Statistics, Table of Contents, and color-coded topic headers.
                4. Output Variation {variation_num} Markdown file.
            """),
            expected_output=f'A Markdown report for Variation {variation_num} as defined in specifications.',
            agent=agent
        )

    def visualization_task(self, agent, insight_file, variation_num):
        return Task(
            description=dedent(f"""
                1. Read {insight_file}.
                2. Generate a self-contained HTML mindmap using D3.js.
                3. Implement collapsible nodes, tooltips, filtration by priority, and legend.
                4. Output Variation {variation_num} HTML file.
            """),
            expected_output=f'A self-contained interactive HTML mindmap for Variation {variation_num}.',
            agent=agent
        )
