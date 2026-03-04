import json
import os
import re
import logging
import time
import copy
import threading
from crewai.tools import BaseTool
import xml.etree.ElementTree as ET
from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict
import httpx

# Global lock — Ollama runs serial GPU inference.
# Both Agent3a and Agent3b threads must take turns so neither times out
# waiting in Ollama's queue.
_ollama_lock = threading.Lock()

def _parse_agent_config():
    """Parse agent-config.xml to get category tags and settings."""
    config_path = os.getenv("CONFIG_PATH", "/app/config/agent-config.xml")
    result = {
        'clientTags': [],
        'projectTags': [],
        'dedupeThreshold': 0.82,
        'emailBodyLimit': 1000,
        'toolOutputLimit': 50000,
        'fileReadLimit': 120000,
        'modelProfile': 'small',
        'summaryLogic': 'code',
        'llmModelHeavy': os.getenv('HEAVY_MODEL', 'llama3.1:8b'),
        'llmModelLight': os.getenv('LIGHT_MODEL', 'mistral'),
        'ollamaBaseUrl': os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434'),
        'escalationKeywords': ['urgent', 'escalate', 'blocker', 'critical', 'overdue',
                               'sla', 'deadline', 'penalty', 'invoice', 'po', 'proposal']
    }
    
    if not os.path.exists(config_path):
        return result
        
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
        
        # Parse Categories
        for cat in root.findall('.//category'):
            name = cat.get('name')
            values = [v.strip() for v in (cat.get('values') or "").split(',')]
            if name == 'client':
                result['clientTags'] = values
            elif name == 'project':
                result['projectTags'] = values
                
        # Parse Settings
        profiles_map = {}
        for profile in root.findall('.//profile'):
            p_name = profile.get('name')
            profiles_map[p_name] = {
                'heavy': profile.get('heavy'),
                'light': profile.get('light')
            }

        for setting in root.findall('.//setting'):
            name = setting.get('name')
            val = setting.get('value')
            if name == 'dedupeThreshold':
                result['dedupeThreshold'] = float(str(val or '0.82'))
            elif name == 'emailBodyLimit':
                result['emailBodyLimit'] = int(str(val or '1000'))
            elif name == 'toolOutputLimit':
                result['toolOutputLimit'] = int(str(val or '50000'))
            elif name == 'fileReadLimit':
                result['fileReadLimit'] = int(str(val or '120000'))
            elif name == 'modelProfile':
                result['modelProfile'] = str(val or 'small')
            elif name == 'summaryLogic':
                result['summaryLogic'] = str(val or 'code')
            elif name == 'llmModelHeavy':
                result['llmModelHeavy'] = str(val or result['llmModelHeavy'])
            elif name == 'llmModelLight':
                result['llmModelLight'] = str(val or result['llmModelLight'])
            elif name == 'ollamaBaseUrl':
                result['ollamaBaseUrl'] = str(val or result['ollamaBaseUrl'])
            elif name == 'escalationKeywords':
                result['escalationKeywords'] = [k.strip().lower() for k in (val or '').split(',') if k.strip()]

        # Resolve models from profile if configured
        active_profile = result.get('modelProfile')
        if active_profile in profiles_map:
            p_cfg = profiles_map[active_profile]
            if p_cfg.get('heavy'): result['llmModelHeavy'] = p_cfg['heavy']
            if p_cfg.get('light'): result['llmModelLight'] = p_cfg['light']

    except Exception:
        pass
    
    return result


def _call_ollama_for_insight(prompt: str, ollama_url: str, model: str, retries: int = 3) -> str:
    """Call Ollama /api/generate with retry and exponential backoff.
    Uses _ollama_lock to prevent concurrent GPU contention when Agent 3a and
    Agent 3b threads both call Ollama at the same time.
    Returns raw response text.
    """
    logger = logging.getLogger(__name__)
    url = ollama_url.rstrip('/') + '/api/generate'
    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': 0.1, 'num_predict': 256, 'num_ctx': 2048}
    }
    for attempt in range(1, retries + 1):
        try:
            # Serialize all Ollama calls — only one thread at a time touches the GPU
            with _ollama_lock:
                logger.debug(f"Ollama call acquired lock (attempt {attempt}): {url}")
                with httpx.Client(timeout=600.0) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get('response', '')
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning(f"Ollama call failed (attempt {attempt}/{retries}): {exc}. Retrying in {wait}s.")
            if attempt < retries:
                time.sleep(wait)
    return ''

def _normalize_subject(subject: str) -> str:
    """Normalize subject to help clustering."""
    s = subject.lower()
    s = re.sub(r'^(re|fw|fwd|aw|reply):\s*', '', s)
    s = re.sub(r'\[.*?\]', '', s)
    return s.strip()

def _clean_body(body: str) -> str:
    """Basic cleanup of email body, stripping trailing threads, HTML tags and excess whitespace."""
    if not body: return ""

    # 1. Truncate trailing reply threads before HTML stripping
    # Common markers for the start of a reply/forward thread (Generic for Outlook, Gmail, etc.)
    markers = [
        r'<hr[^>]*>',                               # HTML horizontal rule
        r'id="(?:divRplyFwdMsg|appendonsend)"',     # Outlook specific identifiers
        r'-----\s*(?:Original Message|Forwarded message)\s*-----', # Common text markers
        r'On\s+.*?\s+wrote:',                       # Gmail/Mobile "On [date], [user] wrote:"
        r'________________________________',        # Horizontal line divider
        # Generic header block: detects a sequence of email headers like From/To/Subject
        # Works for most clients by looking for two or more headers in close proximity.
        r'(?:From|To|Subject|Date|Sent|Cc):\s+.*?\n\s*(?:From|To|Subject|Date|Sent|Cc):'
    ]
    
    for marker in markers:
        match = re.search(marker, body, re.IGNORECASE | re.DOTALL)
        if match:
            # For header blocks, we want to make sure we don't truncate at the very beginning 
            # if the body somehow contains headers (unlikely but safe).
            if match.start() > 10: 
                body = body[:match.start()]
                break

    # 2. Strip HTML tags
    cleaned = re.sub(r'<[^>]+>', ' ', body)
    
    # 3. Decode common HTML entities (minimal)
    cleaned = cleaned.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    
    # 4. Cleanup whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # 5. Remove garbled/invisible characters (like \u034f, \u00ad, zero-width spaces/joiners)
    # These often appear in automated/marketing emails.
    cleaned = re.sub(r'[\u034f\u00ad\u200b\u200c\u200d\u200e\u200f\ufeff]', '', cleaned)
    
    return cleaned.strip()

def _is_noise(email: dict) -> bool:
    """Identify if an email is automated/noise."""
    subject = email.get('subject', '').lower()
    body = (email.get('body', '') or '').lower()
    
    noise_keywords = ["noreply", "no-reply", "automated", "notification", "digest", "newsletter"]
    if any(kw in subject for kw in noise_keywords):
        return True
        
    newsletter_keywords = ["unsubscribe", "view in browser", "privacy policy"]
    if any(kw in body for kw in newsletter_keywords):
        if any(kw in subject or kw in body[:200] for kw in newsletter_keywords):
            return True
            
    return False

def _identify_client_project(email: dict, config: dict):
    """Identify client/project tags from categories first, then fallback."""
    subject = email.get('subject', '').lower()
    body = (email.get('body', '') or '').lower()
    from_addr = email.get('from', '').lower()
    categories = email.get('category', [])
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(',')]
    
    found_clients = []
    found_projects = []

    # 1. Direct match from categories
    client_tags = [t.lower() for t in config.get('clientTags', [])]
    project_tags = [t.lower() for t in config.get('projectTags', [])]

    for cat in categories:
        cat_lower = cat.lower()
        if cat_lower in client_tags:
            # Map back to original case
            found_clients.append(config['clientTags'][client_tags.index(cat_lower)])
        if cat_lower in project_tags:
            found_projects.append(config['projectTags'][project_tags.index(cat_lower)])

    # 2. Fallback to domain/keywords if nothing found in categories
    if not found_clients:
        if '@' in from_addr:
            domain_name = from_addr.split('@')[-1]
            for tag in config.get('clientTags', []):
                if tag.lower() in domain_name:
                    found_clients.append(tag)
                    break
        if not found_clients:
            for tag in config.get('clientTags', []):
                if tag.lower() in subject or tag.lower() in body[:300]:
                    found_clients.append(tag)
                    break

    if not found_projects:
        for tag in config.get('projectTags', []):
            if tag.lower() in subject or tag.lower() in body[:300]:
                found_projects.append(tag)
                break

    primary_client = found_clients[0] if found_clients else "Unknown"
    primary_project = found_projects[0] if found_projects else "Unknown"
    
    return primary_client, primary_project, found_clients, found_projects

class EmailClusteringTool(BaseTool):
    name: str = "semantic_email_clustering_tool"
    description: str = "Clusters emails. Usage: 'file_path' (archive), 'output_file' (optional path to save JSON)."
    
    def _run(self, file_path: Any = None, output_file: Optional[str] = None, **kwargs) -> str:
        actual_path = file_path
        if not actual_path and kwargs:
            actual_path = kwargs.get('file_path')
        if isinstance(actual_path, dict):
            actual_path = actual_path.get('file_path') or actual_path.get('properties', {}).get('file_path')
            
        if not output_file and kwargs:
            output_file = kwargs.get('output_file')

        if not actual_path or not isinstance(actual_path, str):
            return "Error: No valid file_path provided."
            
        if not os.path.exists(actual_path):
            return f"Error: File not found at {actual_path}"
            
        try:
            with open(actual_path, 'r') as f:
                emails = json.load(f)
            
            if not isinstance(emails, list):
                return "Error: JSON must be a list of emails."
            
            config = _parse_agent_config()
            basename = os.path.basename(actual_path)
            date_match = re.search(r'(\d{8})', basename)
            date_str = date_match.group(1) if date_match else "unknown"
            
            valid_emails = []
            noise_emails = []
            for email in emails:
                if _is_noise(email):
                    noise_emails.append(email)
                else:
                    valid_emails.append(email)
            
            cluster_map = {}
            for email in valid_emails:
                subj = email.get('subject', 'No Subject')
                norm_subj = _normalize_subject(subj)
                email['normalizedSubject'] = norm_subj
                
                body = _clean_body(email.get('body', ''))
                body_limit = config.get('emailBodyLimit', 1000)
                if len(body) > body_limit:
                    email['body'] = body[:body_limit] + "... (truncated)"
                else:
                    email['body'] = body
                
                if norm_subj not in cluster_map:
                    cluster_map[norm_subj] = []
                cluster_map[norm_subj].append(email)
            
            clusters = []
            for idx, (topic, email_list) in enumerate(cluster_map.items(), start=1):
                cluster_id = f"cluster-{idx:03d}"
                clients_seen = set()
                projects_seen = set()
                for em in email_list:
                    c, p, _, _ = _identify_client_project(em, config)
                    clients_seen.add(c)
                    projects_seen.add(p)
                
                primary_client = next((c for c in clients_seen if c != "Unknown"), "Unknown")
                primary_project = next((p for p in projects_seen if p != "Unknown"), "Unknown")
                
                cluster_obj = {
                    "clusterId": cluster_id,
                    "topicTitle": topic,
                    "client": primary_client,
                    "project": primary_project,
                    "emailCount": len(email_list),
                    "emails": email_list
                }
                clusters.append(cluster_obj)
            
            result = {
                "date": date_str,
                "totalEmailsRead": len(emails),
                "totalClusters": len(clusters),
                "noiseEmailsExcluded": len(noise_emails),
                "clusters": clusters,
                "noise": noise_emails
            }
            
            json_data = json.dumps(result, indent=2)
            if output_file:
                try:
                    data_dir = os.getenv("DATA_DIR", "/app/data")
                    if not os.path.isabs(output_file):
                        output_file = os.path.join(data_dir, os.path.basename(output_file))
                    with open(output_file, 'w') as f:
                        f.write(json_data)
                    return f"SUCCESS: Clustered data saved to {output_file}"
                except Exception as ex:
                    return f"Error saving output to {output_file}: {str(ex)}"
            
            output_limit = config.get('toolOutputLimit', 50000)
            return json_data[:output_limit]
        except Exception as e:
            return f"Error reading or parsing file: {str(e)}"

class EnhancedFileReadTool(BaseTool):
    name: str = "read_output_json_md_tool"
    description: str = "Reads file content and strips markdown backticks if present."
    
    def _run(self, file_path: Any = None, **kwargs) -> str:
        actual_path = file_path
        if not actual_path and kwargs:
            actual_path = kwargs.get('file_path')
        if isinstance(actual_path, dict):
            actual_path = actual_path.get('file_path') or actual_path.get('properties', {}).get('file_path')

        if not actual_path or not isinstance(actual_path, str):
            return "Error: No valid file_path found in input."

        if os.path.exists(actual_path):
            return self._read_file(actual_path)
        
        data_dir = os.getenv("DATA_DIR", "/app/data")
        alt_path = os.path.join(data_dir, os.path.basename(actual_path))
        if os.path.exists(alt_path):
            return self._read_file(alt_path)
        
        return f"Error: File not found at {actual_path}."
    
    def _read_file(self, path):
        try:
            config = _parse_agent_config()
            read_limit = config.get('fileReadLimit', 120000)
            with open(path, 'r') as f:
                content = f.read()
            
            # Auto-strip Markdown backticks if they exist
            content = content.strip()
            if content.startswith("```"):
                lines = content.splitlines()
                # Find the first line after ```json or similar
                start_idx = 1
                # Find the last line before ```
                end_idx = len(lines) - 1
                if lines[end_idx].strip() == "```":
                    content = "\n".join(lines[start_idx:end_idx]).strip()
            elif "```json" in content:
                # Handle cases where model might have text + markdown
                match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if match:
                    content = match.group(1).strip()
            
            return content[:read_limit]
        except Exception as e:
            return f"Error reading file: {str(e)}"

class HierarchicalGroupingTool(BaseTool):
    name: str = "hierarchical_grouping_tool"
    description: str = "Organizes clusters into Variation 1 or 2 hierarchies and saves to file. Usage: 'clusters_file' (path), 'output_file' (path), 'variation' (1 or 2)."
    
    def _run(self, clusters_file: Any = None, output_file: Optional[str] = None, variation: Any = 1, **kwargs) -> str:
        # Robust parsing
        c_file = clusters_file
        if not c_file and kwargs: c_file = kwargs.get('clusters_file')
        if isinstance(c_file, dict): c_file = c_file.get('clusters_file')
        
        o_file = output_file
        if not o_file and kwargs: o_file = kwargs.get('output_file')
        
        var = variation
        if not var and kwargs: var = kwargs.get('variation')
        try:
            var = int(var)
        except:
            var = 1

        if not c_file or not os.path.exists(c_file):
            return f"Error: Clusters file not found: {c_file}"
        if not o_file:
            return "Error: output_file is required."

        try:
            with open(c_file, 'r') as f:
                data = json.load(f)
            
            clusters = data.get('clusters', [])
            date_str = data.get('date', 'unknown')
            config = _parse_agent_config()
            
            if var == 1:
                # Variation 1: Client > Project > Topic
                result = {
                    "date": date_str,
                    "variation": 1,
                    "grouping": "Client > Project > Topic",
                    "clients": {}
                }
                for cluster in clusters:
                    # Respect multi-client / multi-project if we had that logic, 
                    # but current Agent 1 tool simplifies to primary. 
                    # We'll use the identify logic again to be safe and support duplication if needed.
                    emails = cluster.get('emails', [])
                    # In a real scenario we'd aggregate ALL clients/projects found in the cluster's emails
                    clients = set()
                    projects = set()
                    for email in emails:
                        c, p, cs, ps = _identify_client_project(email, config)
                        for x in cs: clients.add(x)
                        for x in ps: projects.add(x)
                    
                    if not clients: clients.add("Unknown")
                    if not projects: projects.add("Unknown")
                    
                    for client in clients:
                        if client not in result['clients']:
                            result['clients'][client] = {"projects": {}}
                        for project in projects:
                            if project not in result['clients'][client]['projects']:
                                result['clients'][client]['projects'][project] = {"topics": []}
                            
                            topic_node = {
                                "clusterId": cluster.get('clusterId'),
                                "topicTitle": cluster.get('topicTitle'),
                                "emailCount": cluster.get('emailCount'),
                                "emails": emails
                            }
                            result['clients'][client]['projects'][project]['topics'].append(topic_node)
            else:
                # Variation 2: Project > Client > Topic
                result = {
                    "date": date_str,
                    "variation": 2,
                    "grouping": "Project > Client > Topic",
                    "projects": {}
                }
                for cluster in clusters:
                    emails = cluster.get('emails', [])
                    clients = set()
                    projects = set()
                    for email in emails:
                        c, p, cs, ps = _identify_client_project(email, config)
                        for x in cs: clients.add(x)
                        for x in ps: projects.add(x)
                        
                    if not clients: clients.add("Unknown")
                    if not projects: projects.add("Unknown")
                    
                    for project in projects:
                        if project not in result['projects']:
                            result['projects'][project] = {"clients": {}}
                        for client in clients:
                            if client not in result['projects'][project]['clients']:
                                result['projects'][project]['clients'][client] = {"topics": []}
                            
                            topic_node = {
                                "clusterId": cluster.get('clusterId'),
                                "topicTitle": cluster.get('topicTitle'),
                                "emailCount": cluster.get('emailCount'),
                                "emails": emails
                            }
                            result['projects'][project]['clients'][client]['topics'].append(topic_node)

            # Save to file
            data_dir = os.getenv("DATA_DIR", "/app/data")
            if not os.path.isabs(o_file):
                o_file = os.path.join(data_dir, os.path.basename(o_file))
            
            with open(o_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            return f"SUCCESS: Variation {var} grouping saved to {o_file}"
        except Exception as e:
            return f"Error performing hierarchical grouping: {str(e)}"


class ConversationAnalysisTool(BaseTool):
    """
    Agent 3a / 3b tool.
    Reads a conversation-variationN-YYYYMMDD.json file produced by the Hierarchical Grouper,
    calls the heavy LLM (via Ollama) once per topic cluster to produce a structured insight
    object, then writes the complete insight-variationN-YYYYMMDD.json file preserving the
    original hierarchy (Client>Project>Topic for V1, Project>Client>Topic for V2).
    The agent only needs to call this tool once with the correct arguments.
    """
    name: str = "conversation_analysis_tool"
    description: str = (
        "Analyzes ALL topic clusters in a conversation variation file and saves the insight JSON. "
        "Required arguments: 'conversation_file' (absolute path to the conversation JSON), "
        "'output_file' (absolute path to save the insight JSON)."
    )

    # ------------------------------------------------------------------ #
    # Entry point called by CrewAI                                         #
    # ------------------------------------------------------------------ #
    def _run(
        self,
        conversation_file: Any = None,
        output_file: Optional[str] = None,
        **kwargs
    ) -> str:
        logger = logging.getLogger(__name__)

        # --- robust argument extraction (handles dict / positional) ---
        c_file = conversation_file
        if not c_file and kwargs:
            c_file = kwargs.get('conversation_file')
        if isinstance(c_file, dict):
            c_file = c_file.get('conversation_file')

        o_file = output_file
        if not o_file and kwargs:
            o_file = kwargs.get('output_file')
        if isinstance(o_file, dict):
            o_file = o_file.get('output_file')

        # --- validate inputs ---
        if not c_file or not isinstance(c_file, str):
            return "Error: No valid 'conversation_file' path provided."
        if not o_file or not isinstance(o_file, str):
            return "Error: No valid 'output_file' path provided."

        # --- resolve paths ---
        data_dir = os.getenv("DATA_DIR", "/app/data")
        if not os.path.isabs(c_file):
            c_file = os.path.join(data_dir, os.path.basename(c_file))
        if not os.path.isabs(o_file):
            o_file = os.path.join(data_dir, os.path.basename(o_file))

        if not os.path.exists(c_file):
            return f"Error: Conversation file not found at {c_file}"

        # --- load conversation JSON ---
        try:
            with open(c_file, 'r') as fh:
                conv_data = json.load(fh)
        except Exception as exc:
            return f"Error reading conversation file: {exc}"

        config      = _parse_agent_config()
        ollama_url  = config['ollamaBaseUrl']
        model_heavy = config['llmModelHeavy']
        model_light = config['llmModelLight']
        summary_logic = config['summaryLogic']
        variation   = conv_data.get('variation', 1)
        date_str    = conv_data.get('date', 'unknown')
        esc_keywords = config['escalationKeywords']

        logger.info(
            f"ConversationAnalysisTool: variation={variation}, date={date_str}, "
            f"heavy={model_heavy}, light={model_light}, logic={summary_logic}, ollama={ollama_url}"
        )

        # --- deep-copy structure, replace 'emails' arrays with insight objects ---
        result = copy.deepcopy(conv_data)
        errors = []

        if variation == 1:
            # Variation 1: clients > projects > topics
            for client_key, client_val in result.get('clients', {}).items():
                for project_key, project_val in client_val.get('projects', {}).items():
                    new_topics = []
                    for topic in project_val.get('topics', []):
                        insight = self._analyze_topic(
                            topic, esc_keywords, ollama_url, model_heavy, model_light, summary_logic, logger
                        )
                        if isinstance(insight, str):         # error string
                            errors.append(insight)
                        else:
                            new_topics.append(insight)
                    project_val['topics'] = new_topics
        else:
            # Variation 2: projects > clients > topics
            for project_key, project_val in result.get('projects', {}).items():
                for client_key, client_val in project_val.get('clients', {}).items():
                    new_topics = []
                    for topic in client_val.get('topics', []):
                        insight = self._analyze_topic(
                            topic, esc_keywords, ollama_url, model_heavy, model_light, summary_logic, logger
                        )
                        if isinstance(insight, str):
                            errors.append(insight)
                        else:
                            new_topics.append(insight)
                    client_val['topics'] = new_topics

        # --- write output file ---
        try:
            with open(o_file, 'w') as fh:
                json.dump(result, fh, indent=2)
        except Exception as exc:
            return f"Error writing insight file to {o_file}: {exc}"

        summary = f"SUCCESS: Variation {variation} insight file saved to {o_file}"
        if errors:
            summary += f" [{len(errors)} cluster(s) used fallback insight due to LLM errors]"
        logger.info(summary)
        return summary

    # ------------------------------------------------------------------ #
    # Per-topic analysis                                                   #
    # ------------------------------------------------------------------ #
    def _analyze_topic(
        self,
        topic: dict,
        esc_keywords: list,
        ollama_url: str,
        model_heavy: str,
        model_light: str,
        summary_logic: str,
        logger: logging.Logger
    ) -> dict:
        """
        Insight analysis with configurable summary logic.
        """
        cluster_id  = topic.get('clusterId', 'unknown')
        topic_title = topic.get('topicTitle', 'Unknown Topic')
        emails      = topic.get('emails', [])

        # Sort emails chronologically
        emails_sorted = sorted(emails, key=lambda e: e.get('receivedOn', ''))

        # Flatten all text for keyword analysis
        all_text = ' '.join(
            ((e.get('subject', '') or '') + ' ' + (e.get('body', '') or '')).lower()
            for e in emails_sorted
        )

        # --- Escalation & blocker detection via keyword matching ---
        has_escalation = any(kw in all_text for kw in esc_keywords)
        has_blocker = any(kw in all_text for kw in [
            'blocker', 'blocked', 'waiting for', 'pending approval', 'missing',
            'cannot proceed', 'stuck', 'on hold', 'delayed'
        ])

        last_email  = emails_sorted[-1] if emails_sorted else {}
        last_msg_id = last_email.get('messageId', '')
        last_ts     = last_email.get('receivedOn', '')
        last_from   = last_email.get('from', '')
        subject     = last_email.get('subject', topic_title)

        # --- State derivation ---
        overdue_kws  = ['overdue', 'past due', 'deadline', 'sla breach', 'penalty', 'late']
        resolved_kws = ['resolved', 'closed', 'completed', 'done', 'fixed', 'thank you', 'thanks']
        awaiting_kws = ['please confirm', 'awaiting', 'waiting for your', 'please respond', 'kindly']
        sched_kws    = ['scheduled', 'meeting invite', 'calendar', 'agenda', 'next week', 'tomorrow']

        if has_escalation:
            state = 'Active Escalation'
        elif has_blocker:
            state = 'Blocker'
        elif any(kw in all_text for kw in overdue_kws):
            state = 'Overdue'
        elif any(kw in all_text for kw in resolved_kws):
            state = 'Resolved'
        elif any(kw in all_text for kw in awaiting_kws):
            state = 'Awaiting Response'
        elif any(kw in all_text for kw in sched_kws):
            state = 'Scheduled'
        elif len(emails_sorted) > 1:
            state = 'In Progress'
        else:
            state = 'Informational'

        # --- Sentiment derivation ---
        frustrated_kws = ['frustrated', 'disappointed', 'unacceptable', 'this is ridiculous', 'angry']
        concerned_kws  = ['concerned', 'worry', 'worried', 'issue', 'problem', 'risk']
        urgent_kws     = ['urgent', 'asap', 'immediately', 'critical', 'emergency', 'high priority']
        positive_kws   = ['great', 'excellent', 'thank you', 'appreciate', 'well done', 'good progress']

        if any(kw in all_text for kw in frustrated_kws):
            sentiment = 'Frustrated'
        elif any(kw in all_text for kw in urgent_kws) or has_escalation:
            sentiment = 'Urgent'
        elif any(kw in all_text for kw in concerned_kws) or has_blocker:
            sentiment = 'Concerned'
        elif any(kw in all_text for kw in positive_kws):
            sentiment = 'Positive'
        else:
            sentiment = 'Neutral'

        # --- Priority score (1=lowest, 5=highest) ---
        priority = 2
        if has_escalation:
            priority = 5
        elif state == 'Overdue' or state == 'Blocker':
            priority = 4
        elif state in ('Awaiting Response', 'In Progress'):
            priority = 3
        elif state == 'Resolved':
            priority = 1

        # --- Summary Generation ---
        email_count = len(emails_sorted)
        participants = list({e.get('from', '') for e in emails_sorted if e.get('from', '')})
        
        summary = None
        if summary_logic == "none":
            summary = ""
        elif summary_logic == "llm-local-mini":
            summary = self._generate_llm_summary(emails_sorted, topic_title, ollama_url, model_light, logger)
        elif summary_logic == "llm-local-large":
            summary = self._generate_llm_summary(emails_sorted, topic_title, ollama_url, model_heavy, logger)
        elif summary_logic == "llm-api-gemini":
            summary = self._generate_api_summary(emails_sorted, topic_title, "gemini", logger)
        elif summary_logic == "llm-api-openai":
            # This calls OpenAI ChatGPT API (gpt-4o-mini) via LiteLLM
            summary = self._generate_api_summary(emails_sorted, topic_title, "openai", logger)
        
        # If any LLM summary failed or logic is "code" (or default), use deterministic
        if summary is None or summary_logic == "code":
            summary = (
                f"Thread '{subject[:60]}' with {email_count} email(s) from "
                f"{', '.join(participants[:2]) or 'unknown'}. "
                f"Current state: {state}."
            )

        # --- Owner & next action ---
        owner = last_from or 'Unknown'
        if state == 'Awaiting Response':
            recipients = last_email.get('to', [])
            owner = recipients[0] if recipients else last_from
            next_action = f"Response required from {owner}"
        elif state == 'Active Escalation':
            next_action = f"Escalation needs immediate attention from {owner}"
        elif state == 'Blocker':
            next_action = f"Resolve blocker: {owner} must unblock the dependency"
        elif state == 'Overdue':
            next_action = f"Address overdue item: {owner} must take immediate action"
        elif state == 'Resolved':
            next_action = "No further action required — issue resolved"
        else:
            next_action = f"Follow up with {owner} on: {subject[:60]}"

        logger.debug(f"Analyzed cluster {cluster_id} for logic '{summary_logic}': state={state}, priority={priority}")

        return {
            "clusterId": cluster_id,
            "topicTitle": topic_title,
            "summary": summary,
            "state": state,
            "next": next_action,
            "owner": owner,
            "sentiment": sentiment,
            "escalation": has_escalation,
            "escalationDetail": "Escalation keyword detected in email body" if has_escalation else "",
            "blockers": has_blocker,
            "blockerDetail": "Blocker keyword detected in email body" if has_blocker else "",
            "priorityScore": priority,
            "messageId": last_msg_id,
            "timestamp": last_ts
        }

    def _generate_llm_summary(self, emails_sorted, topic_title, ollama_url, model, logger):
        """Use local LLM via Ollama to generate a 2-3 sentence executive summary."""
        try:
            thread_text = []
            for i, em in enumerate(emails_sorted, 1):
                body = (em.get('body', '') or '')[:500]
                thread_text.append(f"[{i}] {em.get('from')} - {em.get('subject')}\n{body}")
            
            prompt = (
                f"Synthesize a 2-3 sentence executive summary of this email thread titled '{topic_title}'.\n"
                f"Focus on core issue, current status and next steps.\n"
                f"Be concise. Do not use conversational filler. Return ONLY the summary.\n\n"
                f"Thread Content:\n" + "\n---\n".join(thread_text) + "\n\n"
                f"EXECUTIVE SUMMARY:"
            )
            
            summary = _call_ollama_for_insight(prompt, ollama_url, model)
            return summary.strip()
        except Exception as exc:
            logger.error(f"Error in local LLM summary: {exc}")
            return None

    def _generate_api_summary(self, emails_sorted, topic_title, provider, logger):
        """Use API-based LLM (Gemini/OpenAI) via LiteLLM to generate a summary."""
        try:
            import litellm
            thread_text = []
            for i, em in enumerate(emails_sorted, 1):
                body = (em.get('body', '') or '')[:800]
                thread_text.append(f"[{i}] {em.get('from')} - {em.get('subject')}\n{body}")

            prompt = (
                f"Synthesize a 2-3 sentence executive summary of this email thread titled '{topic_title}'.\n"
                f"Focus on core issue and status. Be professional and concise.\n\n"
                f"Thread Content:\n" + "\n---\n".join(thread_text) + "\n\n"
                f"EXECUTIVE SUMMARY:"
            )

            model_map = {
                "gemini": "gemini/gemini-1.5-pro",
                "openai": "gpt-4o-mini"
            }
            env_map = {
                "gemini": "GEMINI_API_KEY",
                "openai": "OPENAI_API_KEY"
            }
            
            model_name = model_map.get(provider)
            api_key = os.getenv(env_map.get(provider))
            
            if not api_key or api_key == "NA":
                logger.warning(f"{provider.capitalize()} API key not set or NA.")
                return None
            
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key
            )
            return response.choices[0].message.content.strip()
            
        except ImportError:
            logger.error("litellm module not found. Cannot perform API summary.")
            return None
        except Exception as exc:
            logger.error(f"Error calling {provider} API: {exc}")
            return None

    # ------------------------------------------------------------------ #
    # JSON extraction from LLM response                                  #
    # ------------------------------------------------------------------ #
    def _parse_insight_json(
        self,
        raw: str,
        cluster_id: str,
        topic_title: str,
        last_msg_id: str,
        last_ts: str,
        has_escalation: bool,
        has_blocker: bool
    ) -> dict:
        """Extract JSON from LLM response with multiple fallback strategies."""
        fallback = {
            "clusterId": cluster_id,
            "topicTitle": topic_title,
            "summary": "Insufficient LLM response to analyze this topic.",
            "state": "Unanalyzable",
            "next": "Manual review required",
            "owner": "Unresolved",
            "sentiment": "Neutral",
            "escalation": has_escalation,
            "escalationDetail": "Keyword-detected" if has_escalation else "",
            "blockers": has_blocker,
            "blockerDetail": "Keyword-detected" if has_blocker else "",
            "priorityScore": 3 if has_escalation else 2,
            "messageId": last_msg_id,
            "timestamp": last_ts
        }

        if not raw:
            return fallback

        # Strategy 1: direct JSON parse
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            pass

        # Strategy 2: extract first {...} block
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Strategy 3: strip markdown fences
        stripped = re.sub(r'```(?:json)?', '', raw).strip().rstrip('`').strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        return fallback
