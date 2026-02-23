> This section contains all the prompts for phase 3 of the project. LLM should not process this file.

This architecture is a perfect evolution of your current microservices setup. Since you already have a service generating daily JSON files, adding an agentic layer is essentially creating a **"Processor Service"** that consumes those files and produces high-level insights.

### Part 1: The Master Prompt (For Code Generation)

Copy-paste this prompt into your code generation tool (Antigravity). It is designed to build a **CrewAI** workflow that handles the grouping and summarization logic you described.

```text

You are a Senior AI/ML Software Architect who specializes in created large scale distributed systems using microservices styled architecture. Furthermore, you are also a Project Management expert specializing in email intelligence. Create a CrewAI-based microservice that processes a JSON file containing an array of emails, deduplicate email messages based on their context and process all emails to produce two high-level groups of executive summaries saved in ./data/insight-variation1-YYYYMMDD.json and ./data/insight-variation2-YYYYMMDD.json files. In one summary variation the topics are grouped by Client and then sub grouped by Project. In the other summary variation all topics are grouped by Project and then sub grouped by Client.

DATA STRUCTURE:
The input JSON file ./data/archive-YYYYMMDD.json is an array of email objects. Each email object contains following fields: from, to, cc, category, subject, body, receivedOn, and others.
- The `category` field contains comma separated string tags/labels like 'AB', 'YB' etc (which may be initials of client name) or names of projects (like cba, asba, apy etc).
- Some `category` tags/labels are used to indicate teams (like sales, accounts, elt etc).
- The hint regarding which `category` tags/labels are used to tag clients and which ones for tagging a project or teams are provided in the `agent-config.xml` file under <categories> tag.
- <categories/> will be a collection of <category name='[name of the category]' values="[comma separate list of permissible values]"/>.
   For example:
      <categories>
         <category name='client' values="AB,YB, ..."/>
         <category name='project' values="cba,asba,apy, ..."/>
         <category name='team' values="sales,accounts,elt, ..."/>
      </categories>

OBJECTIVE:
Upon trigger (cron scheduler event, http request, or message queue event) read, process, audit and analyze over 250+ emails in ./data/archives/archive-YYYYMMDD.json file to provide two variations of high-level summaries which will be 1-3 lines per Topic. One summary variation would be items grouped by Client and then by Project and another summary variation will be items grouped by project and then client.

HIERARCHICAL AGENTS TO CREATE:
1. THE CONVERSATION AUDITOR AGENT:
   - Role: Email Conversation Thread & Topic Auditor
   - Backstory: You are an expert at identifying the "hidden story" across multiple emails (subject lines and body). You understand that many emails with different subjects can actually be about the same single issue and also emails with same subject line can be about different issues. You are also an expert at deduplication.
   - Goal: Parse the ./data/archives/archive-YYYYMMDD.json file for today (or as specified) and create two variations of groups for each day. Variation 1: Group emails by Client (from category and/or email IDs) and then sub grouped by Project. Variation 2: Group emails by Project and then sub grouped by Client. Crucially, identify "Topics" for a given project and client. For example: If 15 emails discuss the same 'Server Migration' issues and the emails may have same subject line or sometimes different subject lines, group them into one Topic and then summarize it in 1-3 lines.
   - Logic: Use the 'subject' (ignoring Re:/Fwd:) and 'body' context to deduplicate threads. Note that some emails may have same subject line but different content. Use the 'body' context to deduplicate threads. Sometimes, emails may have different subject lines but same context. Use the 'body' context to deduplicate threads.
   - Task:
      1. Read the ./data/archives/archive-YYYYMMDD.json file. It could be a file with 250+ emails or more and located in some predefined/preconfigured location. By default assume ./data/archives folder.
      2. Read category field to identify the related Client and/or Project name. Use category to confirm the client as email IDs can also be used to identify the client. All categories, whether clients, projects or teams, are defined in the `agent-config.xml` file under <categories> tag. Use this as hint or suggestions only.
      3. You can validate and then expand the client name by checking the email ID domain names in from or to fields. Use category field only to confirm the client names. Categories are surely needed to identify the project name.
      4. Group emails into distinct "Topics" or "Issues." Do not just summarize per email; identify the "Thread" (e.g., if there are 10 emails about a "Database Connection Error," they belong to one Topic).
      5. Output two grouped JSON structures in ./data/conversation-variation1-YYYYMMDD.json and ./data/conversation-variation2-YYYYMMDD.json files like so:
         1. Variation 1: Client -> Project -> Topic -> [list of related emails which may have same subject or different subject lines].
         2. Variation 2: Project -> Client -> Topic -> [list of related emails which may have same subject or different subject lines].

2. THE CONVERSATION ANALYST AGENT:
   - Role: Conversation Context & Sentiment Analyst
   - Backstory: You excel at analyzing conversations (in emails, messages etc) and reading between the lines to find escalations, threats, warnings, blockers, and hidden deadlines.
   - Goal: Read ./data/conversation-variation1-YYYYMMDD.json and ./data/conversation-variation2-YYYYMMDD.json files which has all emails grouped into two hierarchies of topics. Process both these files such that for each Topic group, you investigate and identify: What is the current status? What is the specific 'Ask' (So the Next Step)? Who is the 'Owner' (the person expected to respond)? and other details described in task list below.
   - Output: Format all findings into two clean hierarhies saved in ./data/insight-variation1-YYYYMMDD.json and ./data/insight-variation2-YYYYMMDD.json files like so:
         1. Variation 1: Client -> Project -> Topic -> [An insightful summary json object transformed from the list of emails under that topic in ./data/conversation-variation1-YYYYMMDD.json file].
         2. Variation 2: Project -> Client -> Topic -> [An insightful summary json object transformed from the list of emails under that topic in ./data/conversation-variation2-YYYYMMDD.json file].
   - Task:
      1. Read the ./data/conversation-variation1-YYYYMMDD.json and ./data/conversation-variation2-YYYYMMDD.json files which has all emails grouped into two hierarchies of topics respectively.
      2. For each "Topic" identified by the Conversation Auditor agent, analyze all the emails under that topic to understand the context, sentiment and urgency.
      3. For each "Topic" identified by the Conversation Auditor agent, analyze all the emails under that topic to determine the "Current State": Is it an active escalation, a routine follow-up, a reminder, a meeting invite or a resolved matter?
      4. For each "Topic" identified by the Conversation Auditor agent, analyze all the emails under that topic to identify the "Next Step": What is the single most important action required to move this topic forward?
      5. For each "Topic" identified by the Conversation Auditor agent, analyze all the emails under that topic to identify the "Owner": The person/team responsible for the next step.
      6. Create following insightful summary object for Variation 1 (i.e., for each Client group -> Project subgroup -> Topic sub-subgroup) in the following format, remove all email objects under the topic and save it in ./data/insight-variation1-YYYYMMDD.json file.
         - Topic: [Clear, descriptive title]
         - Summary: [1-3 lines explaining the situation]
         - State: [Current State of the topic]
         - Next: [What needs to happen next]
         - Owner: [The person/team responsible for the next step]
         - Sentiment: [Sentiment of the topic]
         - Escalation: [Is it an escalation?]
         - Blockers: [Are there any blockers?]
         - MessageID: [MessageID of the last email]
         - Timestamp: [Date & Time of last email]
      7. Similarly, create following insightful summary object for Variation 2 (i.e., for each Project group -> Client subgroup -> Topic sub-subgroup) in the following format, remove all email objects under the topic and save it in ./data/insight-variation2-YYYYMMDD.json file.
         - Topic: [Clear, descriptive title based on subject line, email body, and analyzed context]
         - Summary: [1-3 lines explaining the situation]
         - State: [Current State of the topic]
         - Next: [What needs to happen next]
         - Owner: [The person/team responsible for the next step]
         - Sentiment: [Sentiment of the topic]
         - Escalation: [Is it an escalation?]
         - Blockers: [Are there any blockers?]
         - MessageID: [MessageID of the last email]
         - Timestamp: [Date & Time of last email]

3. THE EXECUTIVE REPORTER AGENT:
   - Role: Executive Summary Reporter
   - Backstory: You specialize in creating drafts of "Executive Brevity." for top level officials. Your draft must focus only on high-level impact that may involve financials, PO, Proposals, Invoices, or any blocker/escalated issues along with ownership. It should ignore small low impact items like some trivial bugs or some meeting to be scheduled with teams etc.
   - Goal: Read ./data/insight-variation1-YYYYMMDD.json and ./data/insight-variation2-YYYYMMDD.json files created by Conversation Analyst Agent which and which has all the insights generated for each topic that are grouped into two variations of structural hierarchies.
   - Output: Create two variations of executive summary and saved in ./data/summary-variation1-YYYYMMDD.json and ./data/summary-variation2-YYYYMMDD.json files like so:
      1. Variation 1: Client -> Project -> [Executive Summary of all impactful items processed from the list of topics under this client wise project in ./data/insight-variation1-YYYYMMDD.json file]
      2. Variation 2: Project -> Client -> [Executive Summary of all impactful items processed from the list of topics under this project wise client in ./data/insight-variation2-YYYYMMDD.json file]
   - Task:
      1. Read ./data/insight-variation1-YYYYMMDD.json.
      2. Process variatoin 1 json file for all the topic insights.
      3. Apply priority filter on topics. Only include topics where Escalation is true OR Blockers is non-empty OR the subject involves financials, POs, proposals, invoices, or SLA/deadline mentions.
      4. Generate an executive summary considering all the topics for a given client and a project under that client. Repeat this and create an executive summary for each client and project.
      5. Save the clientwise, project wise executive summary in ./data/summary-variation1-YYYYMMDD.json.
      6. Similarly, read ./data/insight-variation2-YYYYMMDD.json and process it for all the topic insights
      7. Only include topics where Escalation is true OR Blockers is non-empty OR the subject involves financials, POs, proposals, invoices, or SLA/deadline mentions.
      8. Generate an executive summary considering all the topics for a given project and a client under that project. Repeat this and create an executive summary for each project and client.
      9. Save the projectwise, clientwise executive summary in ./data/summary-variation2-YYYYMMDD.json.

4. THE CONVERSATION VISUALIZER AGENT:
   - Role: Conversation Mermaid Visualizer
   - Backstory: You specialize in creating minmap styled trees. Your visualization must be 1-3 lines max, focusing only on high-level impact and ownership.
   - Goal: Use the output files generated by the Conversation Reporter Agent and generate a Mermaid.js 'mindmap' syntax block representing this conversation hierarchy.
   - Output: Generate a Mermaid.js 'mindmap' syntax block representing this hierarchy and save it as ./data/mindmap-variation1-YYYYMMDD.mmd and ./data/mindmap-variation2-YYYYMMDD.mmd files.
   - Task:
      1. Read the Variation 1 summary which is saved in ./data/insight-variation1-YYYYMMDD.json file where topics are grouped under each Client -> Project and generate a Mermaid.js 'mindmap' syntax block representing this hierarchy. The root should be "Daily Summary - [Date]", branching into Clients, then Project Initials, then Topic. Use hover or click callbacks to show Summary, State, Next, and Owner. Based on Escalation and Blockers, show that item in RED to indicate attention. Save this file in ./data/mindmap-variation1-YYYYMMDD.mmd.
      2. Read the Variation 2 summary which is saved in ./data/insight-variation2-YYYYMMDD.json file where topics are grouped under each Project -> Client and generate a Mermaid.js 'mindmap' syntax block representing this hierarchy. The root should be "Daily Summary - [Date]", branching into Projects, then Client Initials, then Topic. Use hover or click callbacks to show Summary, State, Next and Owner. Based on Escalation and Blockers, show that item in RED to indicate attention. Save this file in ./data/mindmap-variation2-YYYYMMDD.mmd.


TECHNICAL REQUIREMENTS:
- Input: Load a local file named './data/archive-YYYYMMDD.json'.
- Framework: Use CrewAI with LangChain or LiteLLM. Use best opensource LLM preferrably locally.
- Process: Sequential.
- Output: Save the final summary as 'insight-variation1-YYYYMMDD.json' and 'insight-variation2 -YYYYMMDD.json' for each type of variation inside ./data folder.

```

---

## Part 2: Architectural Strategy

Since `email-reader-service` already creates the JSON file, implement this AI layer in following 2 ways:

1. **The "Worker" Pattern:**
* **How it works:** Create a new microservice called `crewai-insight-service`.
* **Trigger:** There are 3 triggers like so:
    1. Use a **File Watcher** (like the `watchdog` library in Python)
    2. A **Cron Job** configured to run every 4 hours. Configuration is in `service-config.yaml` file.
    3. On-Demand API (an endpoint exposed by crewai-insight-service) called by email-reader-service. This is explained in subsequent section.
* **Workflow:** When the `email-reader-service` finishes writing the daily JSON, the `crewai-insight-service` detects the new file, runs the CrewAI "Crew," and saves the resulting Markdown/JSON summary.
* **Result:** Your UI simply fetches the *summary* file instead of the raw 250-email JSON.

> Note: You may even map ./data folder inside email-reader-service folder to ./data/archives in crewai-insight-service folder.

2. **The "On-Demand" API:**
* Keep it as a REST endpoint in your `email-reader-service` (e.g., `POST /api/v1/emails/summarize`).
* When you click "Generate Summary" on your Microfrontend, it triggers the CrewAI process.
* *Warning:* AI agents can take 30–90 seconds to process 250 emails. You would need to handle this **asynchronously** (return a `job_id` and poll for the result).
* Add a new tab to your existing `email-reader-ui` called **"Executive Dashboard."** * This UI simply fetches the *already generated* summary from the crewai-insight-service.
* To render the Mind Map, use a React library like `react-mermaid2`. The mindmap will be interactive where on-hover will also show text. Essentially, the code will take the Mermaid string generated by the AI and turn it into a beautiful, clickable diagram.

### Application Configuration

* **Prompt Management:** Store all Crew AI related configurations like "Role", "Backstory", "Goal", "Output", "Logic", "Task" and "Visualization" of your agents in `agent-config.xml` file under <agents> tag. The <agents> tag will be collection of agents (represented by one or more <agent> tags) where each agent will be configured using <agent> tag. The file will reside within the `crewai-insight-service` microservice. This allows you to tweak the "Analyst" agent's personality (e.g., "be more aggressive in flagging escalations") without changing code.
* **Automation:** By using a config file, you can run the service as a **Daemon** (a background process) that wakes up at 8:00 AM every morning, processes the JSON, and has the Mind Map ready for you before you start work.

### Visualization Tip

Since you have a Microfrontend, you can use the **Mermaid.js** library in your UI. The AI agent will output the text-based mind map code, and your UI can render it into a beautiful, interactive diagram automatically.
