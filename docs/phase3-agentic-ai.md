> This section contains all the prompts for phase 2 of the project. LLM should not process this file.

This architecture is a perfect evolution of your current microservices setup. Since you already have a service generating daily JSON files, adding an agentic layer is essentially creating a **"Processor Service"** that consumes those files and produces high-level insights.

### Part 1: The Master Prompt (For Code Generation)

Copy-paste this prompt into your code generation tool (Antigravity). It is designed to build a **CrewAI** workflow that handles the grouping and summarization logic you described.

```text

You are a Senior AI/ML Software Architect who is also a Project Management expert specializing in email intelligence. Create a CrewAI-based microservice that processes a JSON file containing an array of emails, deduplicate email messages based on their context and transform that array into two high-level groups of executive summaries. One summary variation is grouped by Client and then sub grouped by Project. The other summary variation is grouped by Project and then sub grouped by Client.

DATA STRUCTURE:
The JSON contains: [from, to, cc, category, subject, body, receivedOn].
The 'category' field contains string tags like 'AB', 'YB' etc (which may be initials of client name) or names of projects (like cba, asba, apy etc). Some tags are used to indicate teams (like sales, accounts, elt etc). The hint regarding which tags are used to tag clients and which ones for tagging a project or teams are provided in the `agent-config.xml` file under <categories> tag. <categories/> will be collection of <category name='[name of the category]' values="[comma separate list of permissible values]"/>.
For example:
   <categories>
      <category name='client' values="AB,YB, ..."/>
      <category name='project' values="cba,asba,apy, ..."/>
      <category name='team' values="sales,accounts,elt, ..."/>
   </categories>

OBJECTIVE:
Upon trigger (cron scheduler event, http request, or message queue event) read, process, audit and analyze over 250+ emails in ./data/archive-YYYYMMDD.json file to provide two variations of high-level summaries which will be 1-3 lines per Topic. One summary variation would be items grouped by Client and then by Project and another summary variation will be items grouped by project and then client.

HIERARCHICAL AGENTS TO CREATE:
1. THE CONVERSATION AUDITOR AGENT:
   - Role: Email Conversation Thread & Topic Auditor
   - Backstory: You are an expert at identifying the "hidden story" across multiple emails (subject lines and body). You understand that many emails with different subjects can actually be about the same single issue and also emails with same subject line can be about different issues. You are also an expert at deduplication.
   - Goal: Parse the ./data/archive-YYYYMMDD.json file for today (or as specified) and create two variations of groups for each day. Variation 1: Group emails by Client (from category and/or email IDs) and then sub grouped by Project. Variation 2: Group emails by Project and then sub grouped by Client. Crucially, identify "Topics" for a given project and client. For example: If 15 emails discuss the same 'Server Migration' issues and the emails may have same subject line or sometimes different subject lines, group them into one Topic and then summarize it in 1-3 lines.
   - Logic: Use the 'subject' (ignoring Re:/Fwd:) and 'body' context to deduplicate threads. Note that some emails may have same subject line but different content. Use the 'body' context to deduplicate threads. Sometimes, emails may have different subject lines but same context. Use the 'body' context to deduplicate threads.
   - Task:
      1. Read the category field to identify the Client and/or Project name. Use category to confirm the client as email IDs can also be used to identify the client. All categories, whether clients, projects or teams, are defined in the `agent-config.xml` file under <categories> tag. Use this as hint or suggestions only.
      2. You can validate and then expand the client name by checking the email ID domain names in from or to fields. Use category field only to confirm the client names. Categories are surely needed to identify the project name.
      3. Group emails into distinct "Topics" or "Issues." Do not just summarize per email; identify the "Thread" (e.g., if there are 10 emails about a "Database Connection Error," they belong to one Topic).
      4. Output two grouped JSON structures:
         1. Client -> Project -> Topic -> [Summary].
         2. Project -> Client -> Topic -> [Summary].

2. THE CONVERSATION ANALYST AGENT:
   - Role: Conversation Context & Sentiment Analyst
   - Backstory: You excel at reading between the lines to find escalations, threats, warnings, blockers, and hidden deadlines.
   - Goal: For each Topic group, investigate and identify: What is the current status? What is the specific 'Ask'? Who is the 'Owner' (the person expected to respond)?
   - Task:
      1. For each "Topic" identified by the Grouper agent, analyze the sentiment and urgency.
      2. Determine the "Current State": Is it an active escalation, a routine follow-up, a reminder, a meeting invite or a resolved matter?
      3. Identify the "Next Step": What is the single most important action required to move this topic forward?

3. THE CONVERSATION REPORTER AGENT:
   - Role: Conversation Summary Reporter
   - Backstory: You specialize in creating drafts of "Executive Brevity." Your draft must be 1-3 lines max, focusing only on high-level impact and ownership.
   - Goal: Format the findings into two clean hierarchies saved in ./data/insight-variation1-YYYYMMDD.md and ./data/insight-variation2-YYYYMMDD.md files like so:
      1. Variation 1: Client -> Project -> Topic -> [Summary]
      2. Variation 2: Project -> Client -> Topic -> [Summary]
   - Output: Provide a 1-3 line summary per topic. 
   - Visualization: Also generate a Mermaid.js 'mindmap' syntax block representing this hierarchy.
   - Task:
      1. Create one summary (for Variation 1) for each Client -> Project in the following format:
         - Topic Title: [Clear, descriptive title]
         - Summary: [1-3 lines explaining the situation]
         - Expected Response: [What needs to happen next]
         - Owner: [The person/team responsible for the next step]
      2. Create a second summary (for Variation 2) for each Project -> Client in the following format:
         - Topic Title: [Clear, descriptive title]
         - Summary: [1-3 lines explaining the situation]
         - Expected Response: [What needs to happen next]
         - Owner: [The person/team responsible for the next step]
      3. Mandatory Visualization: After the text summaries, generate a Mermaid.js Mind Map code block. The root should be "Daily Summary - [Date]", branching into Clients, then Project Initials, then Topic Titles.

TECHNICAL REQUIREMENTS:
- Input: Load a local file named './data/archive-YYYYMMDD.json'.
- Framework: Use CrewAI with LangChain or LiteLLM. Use best opensource LLM preferrably locally.
- Process: Sequential.
- Output: Save the final summary as 'insight-variation1-YYYYMMDD.md' and 'insight-variation2 -YYYYMMDD.md' for each type of variation inside ./data folder.

```

---

## Part 2: Architectural Strategy

Since `email-reader-service` already creates the JSON file, implement this AI layer in following 2 ways:

1. **The "Worker" Pattern:**
* **How it works:** Create a new microservice called `agentic-insight-service`.
* **Trigger:** There are 3 triggers like so:
    1. Use a **File Watcher** (like the `watchdog` library in Python)
    2. A **Cron Job** configured to run every 10 minutes. Configuration is in `service-config.yaml` file.
    3. On-Demand API (an endpoint exposed by agentic-insight-service) called by email-reader-service. This is explained in subsequent section.
* **Workflow:** When the `email-reader-service` finishes writing the daily JSON, the `agentic-insight-service` detects the new file, runs the CrewAI "Crew," and saves the resulting Markdown/JSON summary.
* **Result:** Your UI simply fetches the *summary* file instead of the raw 250-email JSON.

> Note: You may even map ./data folder inside email-reader-service folder to ./data/archives in agentic-insight-service folder.

2. **The "On-Demand" API:**
* Keep it as a REST endpoint in your `email-reader-service` (e.g., `POST /api/v1/emails/summarize`).
* When you click "Generate Summary" on your Microfrontend, it triggers the CrewAI process.
* *Warning:* AI agents can take 30–90 seconds to process 250 emails. You would need to handle this **asynchronously** (return a `job_id` and poll for the result).
* Add a new tab to your existing `email-reader-ui` called **"Executive Dashboard."** * This UI simply fetches the *already generated* summary from the agentic-insight-service.
* To render the Mind Map, use a React library like `react-mermaid2`. It will take the Mermaid string generated by the AI and turn it into a beautiful, clickable diagram.

### Application Configuration

* **Prompt Management:** Store all Crew AI related configurations like "Role", "Backstory", "Goal", "Output", "Logic", "Task" and "Visualization" of your agents in `agent-config.xml` file under <agents> tag. The <agents> tag will be collection of agents (represented by one or more <agent> tags) where each agent will be configured using <agent> tag. The file will reside within the `agentic-insight-service` microservice. This allows you to tweak the "Analyst" agent's personality (e.g., "be more aggressive in flagging escalations") without changing code.
* **Automation:** By using a config file, you can run the service as a **Daemon** (a background process) that wakes up at 8:00 AM every morning, processes the JSON, and has the Mind Map ready for you before you start work.

### Visualization Tip

Since you have a Microfrontend, you can use the **Mermaid.js** library in your UI. The AI agent will output the text-based mind map code, and your UI can render it into a beautiful, interactive diagram automatically.

**Would you like me to provide a sample of what that `config.yaml` file should look like for your agents?**