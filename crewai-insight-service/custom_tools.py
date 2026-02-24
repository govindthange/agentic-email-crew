import json
import os
import re
from crewai.tools import BaseTool
import xml.etree.ElementTree as ET


def _parse_agent_config():
    """Parse agent-config.xml to get category tags and settings."""
    config_path = os.getenv("CONFIG_PATH", "/app/config/agent-config.xml")
    result = {"clientTags": [], "projectTags": [], "teamTags": [], "dedupeThreshold": 0.82}
    
    if not os.path.exists(config_path):
        return result
    
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
        
        cat_root = root.find('categories')
        if cat_root is not None:
            for cat in cat_root:
                name = cat.get('name')
                values = [v.strip() for v in (cat.get('values') or "").split(',')]
                if name == 'client':
                    result['clientTags'] = values
                elif name == 'project':
                    result['projectTags'] = values
                elif name == 'team':
                    result['teamTags'] = values
        
        set_root = root.find('settings')
        if set_root is not None:
            for setting in set_root:
                if setting.get('name') == 'dedupeThreshold':
                    result['dedupeThreshold'] = float(setting.get('value', '0.82'))
    except Exception:
        pass
    
    return result


def _normalize_subject(subject):
    """Clean common email prefixes and whitespace."""
    if not subject: return ""
    # Remove common prefixes like Re:, Fwd:, etc.
    clean = re.sub(r'(?i)^(re|fwd|fw|aw|reply|feedback):\s*', '', str(subject))
    return clean.strip()

def _clean_body(text):
    """Strip HTML tags and collapse whitespace/newlines to reduce token noise."""
    if not text: return ""
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', str(text))
    # Collapse multiple whitespaces and newlines
    text = re.sub(r'[\s\t\n\r]+', ' ', text)
    return text.strip()


def _identify_client_project(email, config):
    """Determine client and project from category field and email domains."""
    category = email.get('category')
    if category is None:
        cat_parts = []
    elif isinstance(category, list):
        cat_parts = [str(c).strip() for c in category]
    elif isinstance(category, str):
        cat_parts = [c.strip() for c in category.split(',')]
    else:
        cat_parts = [str(category).strip()]
    
    client = "Unknown"
    project = "Unknown"
    
    # Match against config tags
    for part in cat_parts:
        if part in config['clientTags']:
            client = part
        if part in config['projectTags']:
            project = part
    
    # Fallback: try to infer client from sender domain
    if client == "Unknown":
        from_addr = email.get('from', '')
        domain_match = re.search(r'@([\w.-]+)', from_addr)
        if domain_match:
            domain = domain_match.group(1).lower()
            # Use domain name as a hint (first part before TLD)
            domain_parts = domain.split('.')
            if len(domain_parts) >= 2:
                domain_name = domain_parts[0]
                for tag in config['clientTags']:
                    if tag.lower() in domain_name:
                        client = tag
                        break
    
    return client, project


def _is_noise(email):
    """Check if an email is noise (calendar invite, automated alert, newsletter)."""
    subject = (email.get('subject', '') or '').lower()
    body = email.get('body', '') or ''
    category = email.get('category', '') or ''
    
    # Pure calendar invites with no substantive body
    calendar_keywords = ['invitation:', 'accepted:', 'declined:', 'tentative:', 'canceled:']
    if any(subject.startswith(kw) for kw in calendar_keywords) and len(body.strip()) < 100:
        return True
    
    # Automated system alerts with no human action content
    auto_keywords = ['[auto]', 'noreply', 'no-reply', 'automated notification', 'system alert']
    from_addr = (email.get('from', '') or '').lower()
    if any(kw in from_addr or kw in subject for kw in auto_keywords) and len(body.strip()) < 100:
        return True
    
    # Marketing/newsletter with no project/client tags
    newsletter_keywords = ['newsletter', 'unsubscribe', 'marketing']
    if any(kw in subject or kw in body.lower()[:200] for kw in newsletter_keywords):
        has_category = False
        if isinstance(category, str):
            has_category = bool(category.strip())
        elif isinstance(category, list):
            has_category = any(str(c).strip() for c in category)
            
        if not has_category:
            return True
    
    return False


class EmailClusteringTool(BaseTool):
    name: str = "semantic_email_clustering_tool"
    description: str = (
        "Reads the raw email archive and clusters them into topic groups. "
        "Input: absolute file path to the archive JSON. "
        "Output: Raw JSON string of topic clusters."
    )
    
    def _run(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
        try:
            with open(file_path, 'r') as f:
                emails = json.load(f)
            
            if not isinstance(emails, list):
                return "Error: JSON must be a list of emails."
            
            config = _parse_agent_config()
            
            # Extract date from filename (e.g., archive-20260225.json -> 20260225)
            basename = os.path.basename(file_path)
            date_match = re.search(r'(\d{8})', basename)
            date_str = date_match.group(1) if date_match else "unknown"
            
            # Separate noise emails
            valid_emails = []
            noise_emails = []
            for email in emails:
                if _is_noise(email):
                    noise_emails.append(email)
                else:
                    valid_emails.append(email)
            
            # Cluster by normalized subject (string-based) and snippetize bodies
            cluster_map = {}
            for email in valid_emails:
                subj = email.get('subject', 'No Subject')
                norm_subj = _normalize_subject(subj)
                email['normalizedSubject'] = norm_subj
                
                # Clean and Snippetize body for performance and context space
                body = _clean_body(email.get('body', ''))
                if len(body) > 1000:
                    email['body'] = body[:1000] + "... (truncated)"
                else:
                    email['body'] = body
                
                if norm_subj not in cluster_map:
                    cluster_map[norm_subj] = []
                cluster_map[norm_subj].append(email)
            
            # Build spec-compliant clusters array
            clusters = []
            for idx, (topic, email_list) in enumerate(cluster_map.items(), start=1):
                cluster_id = f"cluster-{idx:03d}"
                
                # Determine client/project from the first email (primary)
                # and consolidate across all emails in the cluster
                clients_seen = set()
                projects_seen = set()
                for em in email_list:
                    c, p = _identify_client_project(em, config)
                    clients_seen.add(c)
                    projects_seen.add(p)
                
                # Use the most common non-Unknown value, or "Unknown"
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
            
            return json.dumps(result)[:40000]  # Increased limit for heavy model
        except Exception as e:
            return f"Error reading or parsing file: {str(e)}"


class EnhancedFileReadTool(BaseTool):
    name: str = "Read Output JSON/MD Tool"
    description: str = (
        "Reads a JSON or Markdown file from the data directory. "
        "Accepts either an absolute path or just a filename. "
        "If only a filename is given, it looks in /app/data/ directory. "
        "Returns the file content as a string."
    )
    
    def _run(self, file_path: str) -> str:
        # Try the path as given first
        if os.path.exists(file_path):
            return self._read_file(file_path)
        
        # If not found, try under the data directory
        data_dir = os.getenv("DATA_DIR", "/app/data")
        alt_path = os.path.join(data_dir, os.path.basename(file_path))
        if os.path.exists(alt_path):
            return self._read_file(alt_path)
        
        # List available files to help the agent
        available = []
        if os.path.exists(data_dir):
            available = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
        
        return (
            f"Error: File not found at {file_path} or {alt_path}. "
            f"Available files in {data_dir}: {available}"
        )
    
    def _read_file(self, path):
        try:
            with open(path, 'r') as f:
                content = f.read()
            return content[:25000]
        except Exception as e:
            return f"Error reading file: {str(e)}"
