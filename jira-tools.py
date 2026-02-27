#!/usr/bin/env python3
"""OpenClaw Jira Tools - Automate ticket management via REST API"""

import json
import os
import sys
import base64
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

ENV_FILE = Path(os.path.expanduser("~/.openclaw/workspace/.env"))

# Transition IDs for the KAN board
TRANSITIONS = {
    "idea": 11,
    "todo": 21,
    "in_progress": 31,
    "in_review": 41,
    "done": 51,
}

STATUS_ORDER = ["idea", "todo", "in_progress", "in_review", "done"]


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env


def get_auth():
    env = load_env()
    base_url = env.get("JIRA_BASE_URL", "")
    email = env.get("JIRA_EMAIL", "")
    token = env.get("JIRA_API_TOKEN", "")
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    return base_url, auth


def jira_request(method, endpoint, data=None):
    base_url, auth = get_auth()
    url = f"{base_url}{endpoint}"
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 204:
                return {"ok": True}
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return {"error": error_body, "status": e.code}
    except Exception as e:
        return {"error": str(e)}


def get_issue(key):
    return jira_request("GET", f"/rest/api/3/issue/{key}")


def search_issues(jql, max_results=50):
    return jira_request("POST", "/rest/api/3/search/jql", {
        "jql": jql,
        "maxResults": max_results,
        "fields": ["summary", "status", "issuetype", "description", "parent"],
    })


def transition_issue(key, target_status):
    """Transition an issue to a target status, stepping through intermediate states."""
    target = target_status.lower().replace(" ", "_")
    if target not in TRANSITIONS:
        print(f"Unknown status: {target}. Options: {', '.join(TRANSITIONS.keys())}")
        return False

    # Get current status
    issue = get_issue(key)
    if "error" in issue:
        print(f"Error getting {key}: {issue['error']}")
        return False

    current = issue["fields"]["status"]["name"].lower().replace(" ", "_")
    if current == target:
        print(f"{key} is already {target}")
        return True

    # Find path from current to target
    try:
        current_idx = STATUS_ORDER.index(current)
        target_idx = STATUS_ORDER.index(target)
    except ValueError:
        print(f"Cannot determine path from '{current}' to '{target}'")
        return False

    if target_idx > current_idx:
        path = STATUS_ORDER[current_idx + 1:target_idx + 1]
    else:
        path = STATUS_ORDER[target_idx:current_idx][::-1]

    for step in path:
        tid = TRANSITIONS[step]
        result = jira_request("POST", f"/rest/api/3/issue/{key}/transitions", {
            "transition": {"id": str(tid)}
        })
        if "error" in result:
            print(f"Failed to transition {key} to {step}: {result['error']}")
            return False

    print(f"{key} -> {target}")
    return True


def create_issue(project, summary, issue_type="Story", description="", parent=None):
    data = {
        "fields": {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
    }
    if description:
        data["fields"]["description"] = {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
        }
    if parent:
        data["fields"]["parent"] = {"key": parent}

    result = jira_request("POST", "/rest/api/3/issue", data)
    if "error" in result:
        print(f"Failed to create issue: {result['error']}")
        return None
    key = result.get("key", "")
    print(f"Created {key}: {summary}")
    return key


def board_summary():
    """Print a summary of the board."""
    result = search_issues("project = KAN ORDER BY key ASC", max_results=100)
    if "error" in result:
        print(f"Error: {result['error']}")
        return

    issues = result.get("issues", [])
    by_status = {}
    for issue in issues:
        status = issue["fields"]["status"]["name"]
        if status not in by_status:
            by_status[status] = []
        itype = issue["fields"]["issuetype"]["name"]
        key = issue["key"]
        summary = issue["fields"]["summary"]
        by_status[status].append(f"  [{itype}] {key}: {summary}")

    print(f"=== KAN Board Summary ({len(issues)} issues) ===\n")
    for status in ["Idea", "To Do", "In Progress", "In Review", "Done"]:
        items = by_status.get(status, [])
        print(f"--- {status} ({len(items)}) ---")
        for item in items:
            print(item)
        print()


def sprint_report():
    """Generate a sprint/progress report."""
    result = search_issues("project = KAN ORDER BY key ASC", max_results=100)
    if "error" in result:
        print(f"Error: {result['error']}")
        return

    issues = result.get("issues", [])
    total = len(issues)
    done = sum(1 for i in issues if i["fields"]["status"]["name"] == "Done")
    in_progress = sum(1 for i in issues if i["fields"]["status"]["name"] == "In Progress")
    todo = sum(1 for i in issues if i["fields"]["status"]["name"] in ["To Do", "Idea"])

    epics = [i for i in issues if i["fields"]["issuetype"]["name"] == "Epic"]
    stories = [i for i in issues if i["fields"]["issuetype"]["name"] == "Story"]

    print(f"=== OpenClaw Progress Report ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M ET')}\n")
    print(f"Total issues: {total}")
    print(f"  Done: {done} ({done*100//total}%)")
    print(f"  In Progress: {in_progress}")
    print(f"  Backlog: {todo}\n")

    print(f"Epics: {len(epics)}")
    for e in epics:
        status = e["fields"]["status"]["name"]
        marker = "x" if status == "Done" else ">" if status == "In Progress" else " "
        print(f"  [{marker}] {e['key']}: {e['fields']['summary']} ({status})")

    print(f"\nStories: {len(stories)}")
    for s in stories:
        status = s["fields"]["status"]["name"]
        marker = "x" if status == "Done" else ">" if status == "In Progress" else " "
        print(f"  [{marker}] {s['key']}: {s['fields']['summary']} ({status})")


def print_usage():
    print("OpenClaw Jira Tools")
    print()
    print("Usage:")
    print("  jira-tools.py board                    - Show board summary")
    print("  jira-tools.py report                   - Generate progress report")
    print("  jira-tools.py get KAN-XX               - Get issue details")
    print("  jira-tools.py move KAN-XX done          - Transition issue to status")
    print("  jira-tools.py create 'Summary' [parent] - Create a new story")
    print("  jira-tools.py search 'JQL query'        - Search issues")
    print()
    print(f"Statuses: {', '.join(STATUS_ORDER)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "board":
        board_summary()
    elif cmd == "report":
        sprint_report()
    elif cmd == "get":
        if len(sys.argv) < 3:
            print("Usage: jira-tools.py get KAN-XX")
            sys.exit(1)
        issue = get_issue(sys.argv[2])
        if "error" not in issue:
            f = issue["fields"]
            print(f"Key: {issue['key']}")
            print(f"Type: {f['issuetype']['name']}")
            print(f"Status: {f['status']['name']}")
            print(f"Summary: {f['summary']}")
            desc = f.get("description")
            if desc:
                # Extract text from ADF
                texts = []
                for block in desc.get("content", []):
                    for item in block.get("content", []):
                        if item.get("type") == "text":
                            texts.append(item.get("text", ""))
                if texts:
                    print(f"Description: {' '.join(texts)[:200]}")
        else:
            print(f"Error: {issue['error']}")
    elif cmd == "move":
        if len(sys.argv) < 4:
            print("Usage: jira-tools.py move KAN-XX status")
            sys.exit(1)
        transition_issue(sys.argv[2], sys.argv[3])
    elif cmd == "create":
        if len(sys.argv) < 3:
            print("Usage: jira-tools.py create 'Summary' [parent_key]")
            sys.exit(1)
        summary = sys.argv[2]
        parent = sys.argv[3] if len(sys.argv) > 3 else None
        create_issue("KAN", summary, parent=parent)
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: jira-tools.py search 'JQL'")
            sys.exit(1)
        result = search_issues(sys.argv[2])
        if "error" not in result:
            for i in result.get("issues", []):
                print(f"  {i['key']}: {i['fields']['summary']} ({i['fields']['status']['name']})")
        else:
            print(f"Error: {result['error']}")
    else:
        print_usage()
