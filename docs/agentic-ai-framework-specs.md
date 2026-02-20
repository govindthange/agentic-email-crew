### Implementation Notes for Antigravity

> *"Implement the `crewai-insight-service` as defined in the attached `agentic-ai-framework-specs.md`. Follow the **Architectural Strategy** at the beginning of the file to set up the Worker Pattern and On Demand API Pattern and ensure all Agent outputs strictly match the File Handoff Map. Specifically, ensure Agent 5 produces Markdown for humans while Agent 6 creates the interactive D3.js mindmap. Ensure the service is decoupled from the existing `email-reader-service` and is stable."*

# Architectural Strategy

Implement a multi-agent AI system using following strategy so as to decouple AI layer interacting with the existing `email-reader-service`. The implementation must follow both the patterns explained below, with the **Worker Pattern** being the primary one to be utilized for production stability.

### 1. The "Worker" Pattern (Service-to-Service)

* **Implementation:** Create a new microservice named `crewai-insight-service`.
* **Trigger Mechanism:** The service must support three distinct triggers:
1. **File Watcher:** Use the `watchdog` library to monitor `./data/archives/` for new `archive-YYYYMMDD.json` files.
2. **Cron Job:** A scheduled task (configured in `service-config.yaml`) running every 4 hours to check for unprocessed archives.
3. **On-Demand API:** A REST endpoint (`POST /process`) callable by the `email-reader-service`.


* **Data Integration:** Map the output folder (i.e. `./data`) of the `email-reader-service` to the `./data/archives` input folder of this service.
* **Outcome:** The service executes the CrewAI pipeline and generates the human-readable Markdown reports and interactive HTML mindmaps defined in the Handoff Map.

### 2. The "On-Demand" API (Asynchronous Execution)

* **Endpoint:** A `POST /api/v1/emails/summarize` endpoint handles manual triggers from the UI.
* **Asynchronicity:** Because AI processing can take 30–90 seconds, the service must return a `job_id` immediately and process the request in the background.
* **UI Integration:** The "Executive Dashboard" in the `email-reader-ui` will poll for the status of the `job_id` and fetch the completed reports.

### 3. Mindmap Visualization Strategy

* **Rendering:** Use a React-compatible visualization (such as D3.js as specified in Agent 6) to render the hierarchy.
* **Interactivity:** The visualization must be interactive, supporting click-to-expand nodes and hover-tooltips that display the full `insight` summary (State, Next Step, Owner, and Priority).

---

# Email Intelligence Multi-Agent Framework — Full Specification

---

## Overview

This document defines a multi-agent pipeline that ingests a daily batch of 250+ emails from a structured JSON archive, deduplicates and clusters them into semantic topics, analyzes each topic for context, sentiment and urgency, and finally generates two variations of executive summaries and interactive visual mindmaps — all grouped differently for different reader needs.

---

## Agentic AI Workflow

```
[TRIGGER: cron / HTTP / MQ]
         │
         ▼
┌─────────────────────────┐
│  Agent 1                │
│  Email Preprocessor &   │◄── ./data/archives/archive-YYYYMMDD.json
│  Semantic Deduplicator  │◄── ./config/agent-config.xml
└────────────┬────────────┘
             │ ./data/clusters-YYYYMMDD.json
             ▼
┌─────────────────────────┐
│  Agent 2                │
│  Hierarchical Grouper   │
└────┬───────────────┬────┘
     │               │
     ▼               ▼
conv-variation1   conv-variation2
-YYYYMMDD.json    -YYYYMMDD.json
     │               │
     └───────┬────────┘
             │  (parallel from here)
     ┌───────┴────────┐
     ▼                ▼
┌─────────┐      ┌─────────┐
│Agent 3a │      │Agent 3b │   Conversation Analyst
│Analyst  │      │Analyst  │   (V1 and V2 run in parallel)
│Variation│      │Variation│
│   1     │      │   2     │
└────┬────┘      └────┬────┘
     │                │
     ▼                ▼
insight-v1        insight-v2
-YYYYMMDD.json    -YYYYMMDD.json
     │                │
     ▼                ▼
┌─────────┐      ┌─────────┐
│Agent 4a │      │Agent 4b │   Executive Reporter
│Reporter │      │Reporter │   (V1 and V2 run in parallel)
│Variation│      │Variation│
│   1     │      │   2     │
└────┬────┘      └────┬────┘
     │                │
     ▼                ▼
summary-v1        summary-v2
-YYYYMMDD.json    -YYYYMMDD.json
     │                │
     ▼                ▼
┌─────────┐      ┌─────────┐
│Agent 5a │      │Agent 5b │   Report Formatter  
│Formatter│      │Formatter│   (V1 and V2 run in parallel)
│Variation│      │Variation│
│   1     │      │   2     │
└────┬────┘      └────┬────┘
     │                │
     ▼                ▼
report-v1        report-v2       ← Formatted report outputs
-YYYYMMDD.md    -YYYYMMDD.md
     │                │
     ▼                ▼
┌─────────┐      ┌─────────┐
│Agent 6a │      │Agent 6b │   Mindmap Visualizer
│Visualize│      │Visualize│   (V1 and V2 run in parallel)
│Variation│      │Variation│
│   1     │      │   2     │
└────┬────┘      └────┬────┘
     │                │
     ▼                ▼
mindmap-v1        mindmap-v2
-YYYYMMDD.html    -YYYYMMDD.html
```

**Process Mode:** Sequential between Agent 1 → 2 → (3a ∥ 3b) → (4a ∥ 4b) → (5a ∥ 5b) → (6a ∥ 6b)

---

## Configuration File: `./config/agent-config.xml`

All category definitions are declared here. Agents must read this file at startup.

```xml
<agent-config>

  <categories>
    <!-- Values are the exact strings that appear in the email `category` field -->
    <category name="client"  values="AB, YB, ..." />
    <category name="project" values="cba, asba, apy, ..." />
    <category name="team"    values="sales, accounts, elt, ..." />
  </categories>

  <settings>
    <setting name="archiveDir"         value="./data/archives" />
    <setting name="outputDir"          value="./data" />
    <setting name="dedupeThreshold"    value="0.82" />
    <setting name="llmModelHeavy"      value="qwen2.5:32b" />
    <setting name="llmModelLight"      value="mistral-nemo" />
    <setting name="ollamaBaseUrl"      value="http://localhost:11434" />
    <setting name="escalationKeywords" value="urgent,escalate,blocker,critical,overdue,SLA,deadline,penalty,invoice,PO,proposal" />
  </settings>

</agent-config>
```

---

## Input Data Structure

**File:** `./data/archives/archive-YYYYMMDD.json`

Each element in the root array is an email object with at minimum the following fields:

```jsonc
{
  "messageId":  "<unique-id@domain>",
  "from":       "sender@clientdomain.com",
  "to":         ["recipient1@company.com", "recipient2@company.com"],
  "cc":         ["cc1@company.com"],
  "category":   "AB, cba",           // comma-separated tags from agent-config.xml
  "subject":    "Re: Server Migration Issue",
  "body":       "...",
  "receivedOn": "2025-07-14T10:32:00Z"
  // ...any additional fields are preserved and passed through
}
```

---

## File Handoff Map (Inter-Agent Contracts)

| File | Produced By | Consumed By |
|---|---|---|
| `archive-YYYYMMDD.json` | External / Input | Agent 1 |
| `agent-config.xml` | External / Config | Agent 1, 2 |
| `clusters-YYYYMMDD.json` | Agent 1 | Agent 2 |
| `conversation-variation1-YYYYMMDD.json` | Agent 2 | Agent 3a |
| `conversation-variation2-YYYYMMDD.json` | Agent 2 | Agent 3b |
| `insight-variation1-YYYYMMDD.json` | Agent 3a | Agent 4a, Agent 5a, Agent 6a |
| `insight-variation2-YYYYMMDD.json` | Agent 3b | Agent 4b, Agent 5b, Agent 6b |
| `summary-variation1-YYYYMMDD.json` | Agent 4a | Agent 5a |
| `summary-variation2-YYYYMMDD.json` | Agent 4b | Agent 5b |
| `report-variation1-YYYYMMDD.md` | Agent 5a | Human Reader |
| `report-variation2-YYYYMMDD.md` | Agent 5b | Human Reader |
| `mindmap-variation1-YYYYMMDD.html` | Agent 6a | Human Reader / Dashboard |
| `mindmap-variation2-YYYYMMDD.html` | Agent 6b | Human Reader / Dashboard |

> **Convention:** All intermediate and formatted report files use `.json`. Only the interactive mindmap visualizations use `.html`.

---

## Agents

---

### Agent 1 — Email Preprocessor & Semantic Deduplicator

**Role:** Email Preprocessor & Semantic Deduplication Engine

**Model:** Light model (e.g., `mistral-nemo` via Ollama) combined with a local embedding model (e.g., `nomic-embed-text`) for vector similarity clustering.

**Backstory:**
You are an expert at finding the "hidden story" buried across hundreds of emails. You know that ten emails titled differently can all be about the same broken deployment, and that two emails with the same subject line can be about entirely different matters. You approach deduplication scientifically: you use semantic embeddings to cluster first, then use language reasoning to verify and label each cluster.

**Goal:**
Read the raw email archive for the given date. Normalize subjects, compute semantic embeddings for each email (subject + body combined), cluster similar emails into topic groups using cosine similarity, then use LLM reasoning to validate each cluster, assign a descriptive topic title, and resolve any misclassified emails. Output a flat, deduplicated list of topic clusters.

**Priority Filter (applied during clustering):**
Emails that are pure calendar invites with no substantive body, automated system alerts with no human action content, or marketing/newsletter emails with no project or client category tags should be flagged as `"type": "noise"` and excluded from downstream processing but retained in the output file for auditability.

**Tasks:**

1. Read `./data/archives/archive-YYYYMMDD.json`. If the file does not exist for today's date, halt and log an error: `"Archive not found for YYYYMMDD"`.

2. Read `./config/agent-config.xml` and parse all `<category>` entries. Store them as lookup maps: `clientTags`, `projectTags`, `teamTags`.

3. For each email, normalize the subject line by stripping prefixes `Re:`, `Fwd:`, `FW:`, `RE:`, `AW:` (case-insensitive) and trimming whitespace. Store the normalized subject alongside the original.

4. Concatenate `normalizedSubject + " " + body` for each email and generate a semantic embedding vector using a local embedding model (`nomic-embed-text` via Ollama).

5. Cluster emails using cosine similarity with a configurable threshold (default `0.82` from `agent-config.xml` `dedupeThreshold` setting). Emails above the threshold are candidates for the same topic cluster.

6. For each candidate cluster, use LLM reasoning to:
   - Confirm the cluster is genuinely about the same issue (not just similar vocabulary).
   - Identify any email that was incorrectly pulled into the cluster and move it to its own cluster or a more appropriate one.
   - Assign a concise, descriptive `topicTitle` (e.g., `"Server Migration: DB Connection Failures"`) that reflects the actual issue, not just the subject line.

7. For each email, determine its client and project:
   - Parse the `category` field and match against `clientTags` and `projectTags`.
   - Additionally, extract the domain from the `from` and `to` email addresses. Use domain names to confirm or supplement client identification when `category` is ambiguous.
   - A single email may belong to multiple clients or projects if multiple tags are present. In this case, duplicate the email reference into each relevant group — do not drop it.

8. Output `./data/clusters-YYYYMMDD.json` with the following structure:

```jsonc
{
  "date": "YYYYMMDD",
  "totalEmailsRead": 263,
  "totalClusters": 47,
  "noiseEmailsExcluded": 12,
  "clusters": [
    {
      "clusterId": "cluster-001",
      "topicTitle": "Server Migration: DB Connection Failures",
      "client": "AB",
      "project": "cba",
      "emailCount": 8,
      "emails": [
        {
          "messageId": "<id@domain>",
          "from": "...",
          "to": ["..."],
          "cc": ["..."],
          "category": "AB, cba",
          "subject": "Re: Server Migration Issue",
          "normalizedSubject": "Server Migration Issue",
          "body": "...",
          "receivedOn": "2025-07-14T10:32:00Z"
        }
        // ... remaining emails in this cluster
      ]
    }
    // ... remaining clusters
  ],
  "noise": [
    // emails flagged as noise, kept for audit
  ]
}
```

---

### Agent 2 — Hierarchical Grouper

**Role:** Conversation Thread Hierarchical Organizer

**Model:** Light model (e.g., `mistral-nemo` via Ollama)

**Backstory:**
You are a master librarian of corporate communications. Given a flat list of deduplicated topic clusters, you know exactly how to file them into two different but equally meaningful classification hierarchies — one that a client relationship manager would use, and one that a project delivery manager would prefer.

**Goal:**
Read the flat cluster list from Agent 1 and produce two hierarchically organized JSON files. Variation 1 organizes topics as Client → Project → Topic. Variation 2 organizes topics as Project → Client → Topic. A topic cluster that involves multiple clients or projects must appear in all relevant branches of each hierarchy.

**Tasks:**

1. Read `./data/clusters-YYYYMMDD.json`.

2. Read `./config/agent-config.xml` for the full category taxonomy.

3. For **Variation 1** (Client → Project → Topic):
   - For each cluster, place it under its `client` key, then under its `project` key.
   - If a cluster has multiple clients, place it under each client separately.
   - If a cluster has multiple projects, place it under each project under each client.

4. For **Variation 2** (Project → Client → Topic):
   - For each cluster, place it under its `project` key, then under its `client` key.
   - Apply the same multi-value duplication logic as above.

5. In both variations, each Topic leaf node must carry:
   - `clusterId` (reference back to clusters file)
   - `topicTitle`
   - `emailCount`
   - `emails` array (full email objects as received from Agent 1)

6. Output `./data/conversation-variation1-YYYYMMDD.json`:

```jsonc
{
  "date": "YYYYMMDD",
  "variation": 1,
  "grouping": "Client > Project > Topic",
  "clients": {
    "AB": {
      "projects": {
        "cba": {
          "topics": [
            {
              "clusterId": "cluster-001",
              "topicTitle": "Server Migration: DB Connection Failures",
              "emailCount": 8,
              "emails": [ /* full email objects */ ]
            }
          ]
        }
      }
    }
  }
}
```

7. Output `./data/conversation-variation2-YYYYMMDD.json` with the symmetric structure:

```jsonc
{
  "date": "YYYYMMDD",
  "variation": 2,
  "grouping": "Project > Client > Topic",
  "projects": {
    "cba": {
      "clients": {
        "AB": {
          "topics": [
            {
              "clusterId": "cluster-001",
              "topicTitle": "Server Migration: DB Connection Failures",
              "emailCount": 8,
              "emails": [ /* full email objects */ ]
            }
          ]
        }
      }
    }
  }
}
```

> **Consistency Note:** Because both variations reference the same underlying `clusterId`, downstream agents must ensure that any analysis produced for a given `clusterId` is consistent across both variations. The insight text, state, owner etc. for the same cluster should not contradict each other between Variation 1 and Variation 2.

---

### Agent 3a — Conversation Analyst (Variation 1)

### Agent 3b — Conversation Analyst (Variation 2)

> **Agents 3a and 3b are identical in logic.** They run in parallel: 3a processes `conversation-variation1-YYYYMMDD.json` and 3b processes `conversation-variation2-YYYYMMDD.json`. The instructions below apply to both.

**Role:** Conversation Context, Sentiment & Urgency Analyst

**Model:** Heavy model (e.g., `qwen2.5:32b` via Ollama)

**Backstory:**
You excel at reading between the lines of corporate email threads. You can detect a brewing escalation disguised as a polite follow-up, identify a hidden blocker buried in a status update, and spot an implied deadline that was never explicitly stated. You analyze every email in a topic cluster as a single continuous conversation, not as isolated messages.

**Goal:**
For each Topic cluster in the assigned conversation file, analyze all emails holistically to produce a structured insight object that captures the true state of that topic: what happened, where it stands, who owns the next move, and whether leadership needs to be alerted.

**Priority Scoring (applied per topic):**
Assign each topic a `priorityScore` from 1–5 using these rules:

| Score | Criteria |
|---|---|
| 5 | Active escalation, SLA breach, legal/financial risk, explicit penalty mention |
| 4 | Blocker present, overdue deadline, PO/invoice/proposal stuck or disputed |
| 3 | Follow-up required, implicit deadline within 5 business days |
| 2 | Routine status update, meeting scheduling, informational thread |
| 1 | Noise, resolved matter with no further action needed |

**Tasks:**

1. Read the assigned conversation file (`variation1` or `variation2`).

2. For each Topic cluster, read **all emails** in that cluster as a unified conversation thread, ordered chronologically by `receivedOn`.

3. Determine the **Current State** of the topic. Choose the single most accurate label:
   - `"Active Escalation"` — Someone has explicitly escalated or threatened to escalate.
   - `"Blocker"` — A dependency, approval, or resource is blocking progress.
   - `"Overdue"` — A commitment or deadline has passed without resolution.
   - `"Awaiting Response"` — A question or request was sent and no reply has been received.
   - `"In Progress"` — Active work is ongoing with no immediate blocker.
   - `"Scheduled"` — A meeting, call or review has been arranged.
   - `"Resolved"` — The issue has been closed or acknowledged as complete.
   - `"Informational"` — No action required; thread is context or FYI only.

4. Identify the **Next Step**: the single most important action required to move this topic forward. This must be a concrete, specific statement (e.g., `"John to provide updated delivery timeline by EOD Friday"`) not a vague phrase like `"Follow up required"`.

5. Identify the **Owner**: the specific person or team responsible for the Next Step. Use the email addresses and names in the thread. If ownership is ambiguous, flag it explicitly as `"Owner: Unresolved — [reason]"`.

6. Detect **Escalation**: set to `true` if any of the following are present in any email body in the cluster: escalation language (words from `escalationKeywords` in config), CC'ing of senior leadership not previously on the thread, explicit deadline threats, or mentions of financial penalties or contract breach.

7. Detect **Blockers**: set to `true` if any email in the cluster describes a dependency, missing approval, missing resource, or unresolved technical issue that is preventing progress. Describe the blocker concisely.

8. **Cross-variation consistency:** Each topic has a `clusterId`. If you are Agent 3a, write the `clusterId` into the insight object. Agent 3b must produce insight text that does not contradict 3a for the same `clusterId`. (In practice this is enforced by using the same base cluster data — the hierarchy differs, the analysis must not.)

9. Build the insight object for each topic:

```jsonc
{
  "clusterId":    "cluster-001",
  "topicTitle":   "Server Migration: DB Connection Failures",
  "summary":      "The client AB is experiencing persistent DB connection failures post-migration on the CBA project. Three follow-ups have gone unanswered since Monday.",
  "state":        "Awaiting Response",
  "next":         "DevOps lead (raj@company.com) to share DB config diff by EOD Thursday",
  "owner":        "Raj Mehta <raj@company.com>",
  "sentiment":    "Frustrated",
  "escalation":   true,
  "escalationDetail": "Client CC'd their CTO in the last email",
  "blockers":     true,
  "blockerDetail": "DB config access not yet granted to migration team",
  "priorityScore": 5,
  "messageId":    "<last-email-id@domain>",
  "timestamp":    "2025-07-14T16:45:00Z"
}
```

10. Output `./data/insight-variation1-YYYYMMDD.json` (Agent 3a) preserving the full Client → Project → Topic hierarchy but replacing the `emails` array in each topic with the insight object above:

```jsonc
{
  "date": "YYYYMMDD",
  "variation": 1,
  "grouping": "Client > Project > Topic",
  "clients": {
    "AB": {
      "projects": {
        "cba": {
          "topics": [
            { /* insight object */ }
          ]
        }
      }
    }
  }
}
```

11. Agent 3b outputs `./data/insight-variation2-YYYYMMDD.json` with the symmetric Project → Client → Topic structure.

---

### Agent 4a — Executive Reporter (Variation 1)

### Agent 4b — Executive Reporter (Variation 2)

> **Agents 4a and 4b are identical in logic.** They run in parallel: 4a processes `insight-variation1-YYYYMMDD.json` and 4b processes `insight-variation2-YYYYMMDD.json`.

**Role:** Executive Summary Reporter

**Model:** Heavy model (e.g., `qwen2.5:32b` via Ollama)

**Backstory:** You write for C-suite executives who have two minutes per briefing. You are ruthlessly concise. You know that a CEO does not need to know about a minor UI bug or a team lunch being scheduled — but absolutely must know if a client is threatening to pull a contract, if an invoice is overdue, or if a delivery blocker is putting a project at risk. You synthesize, not transcribe.

**Goal:** For each Client → Project grouping (Variation 1) or Project → Client grouping (Variation 2), read all topic insight objects under that grouping and synthesize a single executive summary paragraph. Include only topics with `priorityScore >= 3`. Discard topics with `priorityScore <= 2` from the summary (they are retained in the insight JSON for reference but not surfaced here).

**Tasks:**

1. Read the assigned insight file.

2. For each Client (Variation 1) or Project (Variation 2), iterate over each sub-group.

3. For each sub-group, collect all topics where `priorityScore >= 3`. If no topics meet this threshold, output a one-line summary: `"No high-priority items identified under this grouping for YYYYMMDD."` — do not omit the grouping entirely.

4. Synthesize a single executive summary for the sub-group covering:
   - The most critical issue and its current state.
   - Any escalations or active blockers, with owner name.
   - Any financial items (PO, invoice, proposal) and their status.
   - The collective recommended action or watch item for leadership.

5. The summary must be 3–6 sentences maximum. Use plain English. No bullet points within the summary text. Use names and specifics, not vague terms.

6. Build the executive summary object per sub-group:

```jsonc
{
  "client": "AB",          // (Variation 1 only)
  "project": "cba",        // sub-group key
  "executiveSummary": "The CBA project for client AB is facing a critical server migration blocker: DB connection failures have been unresolved for 3 days despite three follow-ups, and the client CTO has now been CC'd, indicating an imminent escalation. Raj Mehta (DevOps) is the assigned owner and must deliver the DB config diff by EOD Thursday. Additionally, Invoice #INV-2025-088 for $42,000 remains unpaid and overdue by 12 days — accounts team action required. No proposal or PO items are outstanding for this grouping.",
  "highestPriorityScore": 5,
  "topicsIncluded": ["cluster-001", "cluster-007"],
  "topicsExcluded": ["cluster-012"]   // low priority, excluded from executive view
}
```

7. Output `./data/summary-variation1-YYYYMMDD.json` (Agent 4a):

```jsonc
{
  "date": "YYYYMMDD",
  "variation": 1,
  "grouping": "Client > Project > Executive Summary",
  "clients": {
    "AB": {
      "projects": {
        "cba": { /* executive summary object */ },
        "asba": { /* executive summary object */ }
      }
    },
    "YB": {
      "projects": { /* ... */ }
    }
  }
}
```

8. Agent 4b outputs `./data/summary-variation2-YYYYMMDD.json` with the symmetric Project → Client structure.

---

### Agent 5a — Report Formatter (Variation 1)

### Agent 5b — Report Formatter (Variation 2)

> **Agents 5a and 5b are identical in logic.** They run in parallel: 5a uses `insight-variation1-YYYYMMDD.json` and `summary-variation1-YYYYMMDD.json`; 5b uses the Variation 2 equivalents. These agents produce the **only human-readable formatted report files** in the pipeline (Markdown, consumed directly by humans as structured data).

**Role:** Executive Report Markdown Formatter.

**Model:** Light model (e.g., `mistral-nemo` via Ollama)

**Backstory:** You are a precision formatter. You do not add, remove or interpret any content. Your sole job is to take structured JSON insight and summary data and render it faithfully into a clean, readable, consistently structured **Markdown** report that any executive tool can consume directly, and that is also human-readable as structured data.

**Goal:** Merge the `insight-variationN-YYYYMMDD.json` (containing all topics) and the `summary-variationN-YYYYMMDD.json` (containing executive summaries) into a single coherent **Markdown (.md)** report. The executive summary appears at the top of each grouping section, followed by the detailed topic breakdowns beneath it.

**Tasks:**

1. Read `./data/insight-variation1-YYYYMMDD.json` and `./data/summary-variation1-YYYYMMDD.json` (Agent 5a) or their Variation 2 equivalents (Agent 5b).

2. Render the formatted report JSON as follows. Use this exact structure:

```markdown
# Daily Email Intelligence Report
**Date:** YYYY-MM-DD
**Variation:** 1 — Grouped by Client › Project
**Generated:** [timestamp]

---

## 🏢 Client: AB

### 📁 Project: CBA

> **Executive Summary**
> The CBA project for client AB is facing a critical server migration blocker...
> *(full executive summary text from summary JSON)*

---

#### 🔴 Server Migration: DB Connection Failures
| Field | Detail |
|---|---|
| **State** | Awaiting Response |
| **Summary** | The client AB is experiencing persistent DB connection failures... |
| **Next Step** | DevOps lead (raj@company.com) to share DB config diff by EOD Thursday |
| **Owner** | Raj Mehta |
| **Sentiment** | Frustrated |
| **Escalation** | ✅ Yes — Client CC'd their CTO in the last email |
| **Blockers** | ✅ Yes — DB config access not yet granted to migration team |
| **Priority** | 5 / 5 |
| **Last Message** | 2025-07-14T16:45:00Z |

---

#### 🟡 Invoice #INV-2025-088 Overdue
...

---

#### 🟢 Sprint Planning Meeting Scheduled
...
```

3. **Topic header color coding:**
   - 🔴 Red — `priorityScore` 5 (escalation or critical blocker)
   - 🟠 Orange — `priorityScore` 4 (blocker, overdue, financial at risk)
   - 🟡 Yellow — `priorityScore` 3 (follow-up required, implicit deadline)
   - 🟢 Green — `priorityScore` 1–2 (routine / resolved / informational)

4. Include all topics regardless of priority score in the report detail section. The executive summary above each project section already filters to high-priority only. The detail section gives the full picture for those who want it. For each grouping, display the **Executive Summary** text from the summary JSON within a Markdown blockquote (`>`).

5. Add a **Table of Contents** at the top of the document linking to each Client/Project section (Variation 1) or Project/Client section (Variation 2).

6. Add a **Summary Statistics** block immediately after the document header:

```markdown
## Summary Statistics
| Metric | Value |
|---|---|
| Total Emails Processed | 263 |
| Noise Emails Excluded | 12 |
| Unique Topics Identified | 47 |
| High Priority Topics (4–5) | 11 |
| Escalations | 4 |
| Active Blockers | 6 |
| Clients Covered | 5 |
| Projects Covered | 8 |
```

7. Output:
   - Agent 5a → `./data/report-variation1-YYYYMMDD.md`
   - Agent 5b → `./data/report-variation2-YYYYMMDD.md`

---

### Agent 6a — Mindmap Visualizer (Variation 1)

### Agent 6b — Mindmap Visualizer (Variation 2)

> **Agents 6a and 6b are identical in logic.** They run in parallel on their respective  formatted report JSON and summary JSON files.

**Role:** Interactive Mindmap HTML Visualizer

**Model:** Light model (e.g., `mistral-nemo` via Ollama) for content formatting; no LLM reasoning required — this is a structural rendering task.

**Backstory:** You specialize in translating hierarchical data into self-contained, interactive HTML visualizations that need no external dependencies. You know that Mermaid.js `mindmap` diagrams do not support hover tooltips natively, so you build lightweight HTML pages using inline JavaScript (vanilla D3.js or a collapsible tree library) that render the hierarchy with click-to-expand nodes and tooltip overlays showing topic details.

**Goal:** Produce a self-contained single-file HTML mindmap visualization for each variation. The root node is `"Daily Summary — YYYY-MM-DD"`. Nodes are color-coded by priority. Clicking or hovering a topic node reveals a tooltip with the full insight summary.

**Technical Approach:** Use an inline `<script>` block embedding D3.js (loaded from CDN) to render a collapsible radial tree or force-directed graph. Do not use Mermaid.js `mindmap` syntax for the interactive version — it does not support hover/click behaviors.

**Optionally**, also generate a static Mermaid.js block (non-interactive, for embedding in docs) and include it in a `<details>` / `<summary>` collapsible section at the bottom of the HTML file.

**Tasks:**

1. Read the assigned summary JSON file and insight JSON file.

2. Build the node tree:
   - **Root:** `"Daily Summary — YYYY-MM-DD"`
   - **Level 1:** Clients (Variation 1) or Projects (Variation 2)
   - **Level 2:** Projects under each Client (V1) or Clients under each Project (V2)
   - **Level 3:** Topics (leaf nodes)

3. Node color coding per topic:
   - 🔴 `#e74c3c` — `priorityScore` 5
   - 🟠 `#e67e22` — `priorityScore` 4
   - 🟡 `#f1c40f` — `priorityScore` 3
   - 🟢 `#27ae60` — `priorityScore` 1–2

4. Tooltip content on hover/click for each topic node:

```
[Topic Title]
─────────────────────
State:    Awaiting Response
Summary:  The client AB is experiencing...
Next:     Raj to share DB config diff by EOD Thu
Owner:    Raj Mehta
Priority: 5/5  |  ⚠ Escalation  |  🚧 Blocker
```

5. Level 1 and Level 2 nodes show aggregate stats in their tooltip:
   - Number of topics
   - Number of escalations
   - Highest priority score in this branch

6. Include a **legend** in the bottom-right corner of the visualization.

7. Include a **filter control panel** in the top-right corner with checkboxes:
   - Show Priority 5 (default: checked)
   - Show Priority 4 (default: checked)
   - Show Priority 3 (default: checked)
   - Show Priority 1–2 (default: unchecked — hidden by default to reduce noise)

8. The HTML file must be fully self-contained (no external file dependencies other than D3.js loaded via CDN). It must render correctly when opened directly in a browser without a local server.

9. Output:
   - Agent 6a → `./data/mindmap-variation1-YYYYMMDD.html`
   - Agent 6b → `./data/mindmap-variation2-YYYYMMDD.html`

---

## Technical Implementation Notes

### Framework

**Primary recommendation: LangGraph** (LangChain ecosystem)
- Native support for parallel branches (Agents 3a/3b, 4a/4b, 5a/5b, 6a/6b run in parallel)
- Full control over the DAG execution graph
- Better suited for production-grade pipelines with 250+ emails and multiple LLM calls

**Alternative: CrewAI**
- Use `Process.sequential` for Agent 1 → 2
- Use `async_execution=True` for all parallel Variation 1 / Variation 2 agent pairs (3a/3b onward)
- Simpler setup, acceptable for initial prototyping

### LLM Configuration (Ollama)

```python
# Two-model strategy
LIGHT_MODEL  = "mistral-nemo"    # Agents 1, 2, 5a, 5b, 6a, 6b
HEAVY_MODEL  = "qwen2.5:32b"     # Agents 3a, 3b, 4a, 4b

# Embedding model for Agent 1 deduplication
EMBED_MODEL  = "nomic-embed-text"

# Ollama base URL
OLLAMA_URL   = "http://localhost:11434"
```

### Trigger Mechanisms

The pipeline supports three trigger modes, selectable via config:

```python
# 1. Cron (daily at 07:00)
# 2. HTTP POST /process?date=YYYYMMDD
# 3. Message Queue (RabbitMQ / Redis Streams topic: email.archive.ready)
```

### Error Handling

- If any intermediate file is missing at the start of an agent, halt that agent and log a structured error. Do not produce partial output files.
- If an LLM call fails or times out, retry up to 3 times with exponential backoff.
- If a topic cluster cannot be analyzed (e.g., body is empty for all emails), insert a placeholder insight with `state: "Unanalyzable"` and `summary: "Insufficient content to analyze"` — do not skip the topic entirely.
- All agent runs must produce a run log at `./logs/run-YYYYMMDD-HHmmss.log`.

### Final Output Files (Human Deliverables)

| File | Description |
|---|---|
| `./data/report-variation1-YYYYMMDD.md` | Formatted report: Client → Project → Topics |
| `./data/report-variation2-YYYYMMDD.md` | Formatted report: Project → Client → Topics |
| `./data/mindmap-variation1-YYYYMMDD.html` | Interactive mindmap: Client → Project → Topics |
| `./data/mindmap-variation2-YYYYMMDD.html` | Interactive mindmap: Project → Client → Topics |

### Intermediate Files (Machine-to-Machine, Not for Human Distribution)

| File | Description |
|---|---|
| `./data/clusters-YYYYMMDD.json` | Flat deduplicated topic clusters |
| `./data/conversation-variation1-YYYYMMDD.json` | Grouped emails V1 |
| `./data/conversation-variation2-YYYYMMDD.json` | Grouped emails V2 |
| `./data/insight-variation1-YYYYMMDD.json` | Topic insights V1 |
| `./data/insight-variation2-YYYYMMDD.json` | Topic insights V2 |
| `./data/summary-variation1-YYYYMMDD.json` | Executive summaries V1 |
| `./data/summary-variation2-YYYYMMDD.json` | Executive summaries V2 |