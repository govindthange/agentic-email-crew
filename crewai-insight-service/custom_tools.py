import json
import os
import re
import logging
from crewai.tools import BaseTool
import xml.etree.ElementTree as ET
from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict

def _parse_agent_config():
    """Parse agent-config.xml to get category tags and settings."""
    config_path = os.getenv("CONFIG_PATH", "/app/config/agent-config.xml")
    result = {
        'clientTags': [],
        'projectTags': [],
        'dedupeThreshold': 0.82,
        'emailBodyLimit': 1000,
        'toolOutputLimit': 50000,
        'fileReadLimit': 120000
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
    except Exception:
        pass
    
    return result

def _normalize_subject(subject: str) -> str:
    """Normalize subject to help clustering."""
    s = subject.lower()
    s = re.sub(r'^(re|fw|fwd|aw|reply):\s*', '', s)
    s = re.sub(r'\[.*?\]', '', s)
    return s.strip()

def _clean_body(body: str) -> str:
    """Basic cleanup of email body."""
    if not body: return ""
    cleaned = re.sub(r'\n\s*\n', '\n', body)
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
