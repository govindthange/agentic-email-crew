from crewai import Task
from textwrap import dedent

class InsightTasks:
    def preprocessing_task(self, agent, input_file, output_file):
        return Task(
            description=dedent(f"""\
                Task: Call the 'semantic_email_clustering_tool' for {input_file} and return the JSON.
                
                Mandatory:
                1. Call the tool.
                2. Return the exact JSON object from the tool. 
                3. Do NOT add any words, text, or summaries.
                4. Do NOT use markdown code blocks.
                5. Output must be raw JSON only.
            """),
            expected_output=dedent("""\
                A raw JSON object (no markdown, no explanation) with these exact keys:
                {
                    "date": "YYYYMMDD",
                    "totalEmailsRead": <number>,
                    "totalClusters": <number>,
                    "noiseEmailsExcluded": <number>,
                    "clusters": [
                        {
                            "clusterId": "cluster-001",
                            "topicTitle": "descriptive title",
                            "client": "client tag",
                            "project": "project tag",
                            "emailCount": <number>,
                            "emails": [<email objects>]
                        }
                    ],
                    "noise": [<noise email objects>]
                }
            """),
            agent=agent,
            output_file=output_file
        )

    def grouping_task(self, agent, clusters_file, output_file_v1, output_file_v2):
        return Task(
            description=dedent(f"""\
                CRITICAL INSTRUCTION: You MUST use the 'Read Output JSON/MD Tool' to read the file: {clusters_file}
                This is the clusters JSON file produced by the previous agent.
                
                DO NOT invent or guess the data. Read the actual file, then:
                1. Parse all clusters from the JSON.
                2. Organize them into Client > Project > Topic hierarchy (Variation 1).
                3. Organize them into Project > Client > Topic hierarchy (Variation 2).
                
                If a cluster has multiple clients or projects, place it under each relevant branch.
                
                Your final answer must be ONLY valid RAW JSON with Variation1 and Variation2 combined.
                Do NOT include "Final Answer:".
                Do NOT use markdown code blocks.
                Do NOT add any sentences.
            """),
            expected_output=dedent("""\
                A raw JSON object with Variation 1 and Variation 2 hierarchies:
                {
                    "variation1": {
                        "date": "YYYYMMDD",
                        "variation": 1,
                        "grouping": "Client > Project > Topic",
                        "clients": { ... }
                    },
                    "variation2": {
                        "date": "YYYYMMDD", 
                        "variation": 2,
                        "grouping": "Project > Client > Topic",
                        "projects": { ... }
                    }
                }
            """),
            agent=agent,
            output_file=output_file_v1  # CrewAI only supports 1 output_file per task
        )

    def analysis_task(self, agent, variation_file, variation_num, output_file):
        return Task(
            description=dedent(f"""\
                CRITICAL INSTRUCTION: You MUST use the 'Read Output JSON/MD Tool' to read the file: {variation_file}
                DO NOT hallucinate. Use the real data to:
                1. For each Topic cluster, analyze all emails chronologically.
                2. Determine Current State, Next Step, Owner, Sentiment, Escalation, and Blockers.
                3. Assign Priority Score (1-5).
                4. Output Variation {variation_num} insight JSON.
            """),
            expected_output=f'A JSON object for Variation {variation_num} preserving hierarchy with detailed insight objects at topic level (based entirely on actual read data).',
            agent=agent,
            output_file=output_file
        )

    def reporting_task(self, agent, insight_file, variation_num, output_file):
        return Task(
            description=dedent(f"""\
                CRITICAL INSTRUCTION: You MUST use the 'Read Output JSON/MD Tool' to read the file: {insight_file}
                DO NOT guess. Read the insights to:
                1. For each group, synthesize a single executive summary paragraph (3-6 sentences).
                2. Only include items with priorityScore >= 3.
                3. Output Variation {variation_num} summary JSON.
            """),
            expected_output=f'A JSON object for Variation {variation_num} containing executive summaries for each grouping derived from the actual insight file.',
            agent=agent,
            output_file=output_file
        )

    def formatting_task(self, agent, insight_file, summary_file, variation_num, output_file):
        return Task(
            description=dedent(f"""\
                CRITICAL INSTRUCTION: You MUST use the 'Read Output JSON/MD Tool' to read BOTH files:
                1. {insight_file}
                2. {summary_file}
                Merge the real data:
                1. Format as a comprehensive Markdown report.
                2. Include Summary Statistics, Table of Contents, and color-coded topic headers.
                3. Output Variation {variation_num} Markdown file.
            """),
            expected_output=f'A Markdown report for Variation {variation_num} formatted based on the actual inputs and specifications.',
            agent=agent,
            output_file=output_file
        )

    def visualization_task(self, agent, insight_file, variation_num, output_file):
        return Task(
            description=dedent(f"""\
                CRITICAL INSTRUCTION: You MUST use the 'Read Output JSON/MD Tool' to read the file: {insight_file}
                Based directly on the real JSON data:
                1. Generate a self-contained HTML mindmap using D3.js.
                2. Implement collapsible nodes, tooltips, filtration by priority, and legend.
                3. Output Variation {variation_num} HTML file.
            """),
            expected_output=f'A self-contained interactive D3.js HTML mindmap for Variation {variation_num} rendering the actual insight data.',
            agent=agent,
            output_file=output_file
        )
