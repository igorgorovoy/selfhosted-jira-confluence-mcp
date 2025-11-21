import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

# --------------------------------------------------------------------
#  Env / config
# --------------------------------------------------------------------

load_dotenv()  # читає .env, якщо є

@dataclass
class ConfluenceConfig:
    base_url: str
    username: str
    api_token: str


@dataclass
class JiraConfig:
    base_url: str
    username: str
    api_token: str


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def get_confluence_config() -> ConfluenceConfig:
    return ConfluenceConfig(
        base_url=_get_env("CONFLUENCE_BASE_URL"),
        username=_get_env("CONFLUENCE_USERNAME"),
        api_token=_get_env("CONFLUENCE_API_TOKEN"),
    )


def get_jira_config() -> JiraConfig:
    return JiraConfig(
        base_url=_get_env("JIRA_BASE_URL"),
        username=_get_env("JIRA_USERNAME"),
        api_token=_get_env("JIRA_API_TOKEN"),
    )

# --------------------------------------------------------------------
#  Low-level REST clients
# --------------------------------------------------------------------


class ConfluenceClient:
    """
    Simple Confluence REST client for Server/Data Center 6.x.

    Expects:
      - base_url like: https://confluence.example.com
      - REST base: {base_url}/rest/api
    """

    def __init__(self, config: ConfluenceConfig):
        self.base_url = config.base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (config.username, config.api_token)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        return f"{self.base_url}/rest/api{path}"

    def get_page(self, page_id: str, expand: str = "body.storage,version,space") -> Dict[str, Any]:
        resp = self.session.get(self._url(f"/content/{page_id}"), params={"expand": expand})
        resp.raise_for_status()
        return resp.json()

    def search_pages(self, cql: str, limit: int = 25, start: int = 0) -> Dict[str, Any]:
        resp = self.session.get(
            self._url("/content/search"),
            params={"cql": cql, "limit": limit, "start": start, "expand": "space,version"},
        )
        resp.raise_for_status()
        return resp.json()

    def get_spaces(self, limit: int = 100, start: int = 0) -> Dict[str, Any]:
        resp = self.session.get(
            self._url("/space"),
            params={"limit": limit, "start": start, "expand": "description.plain,homepage"},
        )
        resp.raise_for_status()
        return resp.json()

    def create_page(
        self,
        space_key: str,
        title: str,
        body_storage: str,
        parent_page_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body_storage,
                    "representation": "storage",
                }
            },
        }

        if parent_page_id:
            payload["ancestors"] = [{"id": parent_page_id}]

        resp = self.session.post(self._url("/content"), json=payload)
        resp.raise_for_status()
        return resp.json()

    def delete_page(self, page_id: str, status: str = "current") -> None:
        """
        Delete a Confluence page by ID.

        By default deletes the current version. Confluence may return 204 No Content on success.
        """
        resp = self.session.delete(self._url(f"/content/{page_id}"), params={"status": status})
        resp.raise_for_status()


class JiraClient:
    """
    Simple Jira REST client for Server/Data Center 8.x.

    Expects:
      - base_url like: https://jira.example.com
      - REST base: {base_url}/rest/api/2
    """

    def __init__(self, config: JiraConfig):
        self.base_url = config.base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (config.username, config.api_token)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        # Jira 8.8.0 uses /rest/api/2
        return f"{self.base_url}/rest/api/2{path}"

    def get_issue(self, issue_key: str, fields: Optional[str] = None) -> Dict[str, Any]:
        params = {"fields": fields} if fields else None
        resp = self.session.get(self._url(f"/issue/{issue_key}"), params=params)
        resp.raise_for_status()
        return resp.json()

    def search_issues(self, jql: str, max_results: int = 50, start_at: int = 0) -> Dict[str, Any]:
        payload = {
            "jql": jql,
            "maxResults": max_results,
            "startAt": start_at,
        }
        resp = self.session.post(self._url("/search"), json=payload)
        resp.raise_for_status()
        return resp.json()

    def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
            }
        }
        if description:
            payload["fields"]["description"] = description

        resp = self.session.post(self._url("/issue"), json=payload)
        resp.raise_for_status()
        return resp.json()

    def delete_issue(self, issue_key: str, delete_subtasks: bool = False) -> None:
        """
        Delete Jira issue by key.

        If delete_subtasks is True, Jira will also delete all subtasks of the issue.
        """
        params = {"deleteSubtasks": str(delete_subtasks).lower()}
        resp = self.session.delete(self._url(f"/issue/{issue_key}"), params=params)
        resp.raise_for_status()


# --------------------------------------------------------------------
#  MCP server (FastMCP)
# --------------------------------------------------------------------

mcp = FastMCP("Atlassian MCP (Jira + Confluence)")

# Lazy singletons (щоб при падінні env не валився імпорт модуля)


_confluence_client: Optional[ConfluenceClient] = None
_jira_client: Optional[JiraClient] = None


def get_confluence_client_singleton() -> ConfluenceClient:
    global _confluence_client
    if _confluence_client is None:
        _confluence_client = ConfluenceClient(get_confluence_config())
    return _confluence_client


def get_jira_client_singleton() -> JiraClient:
    global _jira_client
    if _jira_client is None:
        _jira_client = JiraClient(get_jira_config())
    return _jira_client


# ---------------- Confluence tools -----------------


@mcp.tool()
def confluence_get_page(page_id: str) -> Dict[str, Any]:
    """
    Get a Confluence page by ID (6.14.1 Server/DC).

    Returns basic metadata + full storage body.
    """
    client = get_confluence_client_singleton()
    try:
        data = client.get_page(page_id)
    except requests.RequestException as e:
        raise RuntimeError(f"Confluence get_page failed: {e}") from e

    body_storage = (
        (data.get("body") or {}).get("storage") or {}
    ).get("value")

    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "space": (data.get("space") or {}).get("key"),
        "version": (data.get("version") or {}).get("number"),
        "status": data.get("status"),
        "body_storage": body_storage,
        "raw": data,
    }


@mcp.tool()
def confluence_search_pages(cql: str, limit: int = 25, start: int = 0) -> Dict[str, Any]:
    """
    Search Confluence pages via CQL.

    Example CQL:
      space = "ENG" AND type = "page" AND title ~ "Karpenter"
    """
    client = get_confluence_client_singleton()
    try:
        data = client.search_pages(cql=cql, limit=limit, start=start)
    except requests.RequestException as e:
        raise RuntimeError(f"Confluence search failed: {e}") from e

    results: List[Dict[str, Any]] = []
    for item in data.get("results", []):
        results.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "space": (item.get("space") or {}).get("key"),
                "version": (item.get("version") or {}).get("number"),
                "status": item.get("status"),
                "type": item.get("type"),
                "url": item.get("_links", {}).get("self"),
            }
        )

    return {
        "size": data.get("size"),
        "limit": data.get("limit"),
        "results": results,
        "raw": data,
    }


@mcp.tool()
def confluence_get_spaces(limit: int = 100, start: int = 0) -> Dict[str, Any]:
    """
    Get list of Confluence spaces.

    Returns information about all available spaces in Confluence.
    """
    client = get_confluence_client_singleton()
    try:
        data = client.get_spaces(limit=limit, start=start)
    except requests.RequestException as e:
        raise RuntimeError(f"Confluence get_spaces failed: {e}") from e

    spaces: List[Dict[str, Any]] = []
    for space in data.get("results", []):
        spaces.append(
            {
                "key": space.get("key"),
                "name": space.get("name"),
                "type": space.get("type"),
                "status": space.get("status"),
                "description": (space.get("description") or {}).get("plain"),
                "homepage": (space.get("homepage") or {}).get("id"),
                "url": space.get("_links", {}).get("self"),
            }
        )

    return {
        "size": data.get("size"),
        "limit": data.get("limit"),
        "total": len(spaces),
        "spaces": spaces,
        "raw": data,
    }


@mcp.tool()
def confluence_create_page(
    space_key: str,
    title: str,
    body_storage: str,
    parent_page_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a Confluence page (storage format).

    WARNING: this actually creates content in Confluence.
    """
    client = get_confluence_client_singleton()
    try:
        data = client.create_page(
            space_key=space_key,
            title=title,
            body_storage=body_storage,
            parent_page_id=parent_page_id,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Confluence create_page failed: {e}") from e

    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "space": (data.get("space") or {}).get("key"),
        "status": data.get("status"),
        "links": data.get("_links"),
        "raw": data,
    }


@mcp.tool()
def confluence_delete_page(page_id: str, status: str = "current") -> Dict[str, Any]:
    """
    Delete a Confluence page by ID (6.14.1 Server/DC).

    WARNING: this actually deletes content in Confluence. Some configurations move the page
    to trash for certain status values; others may remove it permanently.
    """
    client = get_confluence_client_singleton()
    try:
        client.delete_page(page_id=page_id, status=status)
    except requests.RequestException as e:
        raise RuntimeError(f"Confluence delete_page failed: {e}") from e

    return {
        "id": page_id,
        "status": "deleted",
        "delete_status_param": status,
    }


# ---------------- Jira tools -----------------


@mcp.tool()
def jira_get_issue(issue_key: str, fields: Optional[str] = None) -> Dict[str, Any]:
    """
    Get Jira issue by key (Jira Server/DC 8.8.0).

    `fields` is optional comma-separated list of fields, e.g. "summary,status,assignee".
    """
    client = get_jira_client_singleton()
    try:
        data = client.get_issue(issue_key=issue_key, fields=fields)
    except requests.RequestException as e:
        raise RuntimeError(f"Jira get_issue failed: {e}") from e

    fields_data = data.get("fields") or {}
    return {
        "key": data.get("key"),
        "id": data.get("id"),
        "self": data.get("self"),
        "summary": fields_data.get("summary"),
        "status": (fields_data.get("status") or {}).get("name"),
        "issuetype": (fields_data.get("issuetype") or {}).get("name"),
        "project_key": ((fields_data.get("project") or {}).get("key")),
        "assignee": (fields_data.get("assignee") or {}).get("displayName"),
        "raw": data,
    }


@mcp.tool()
def jira_search_issues(
    jql: str,
    max_results: int = 50,
    start_at: int = 0,
) -> Dict[str, Any]:
    """
    Search Jira issues by JQL.

    Example JQL:
      project = L2S AND statusCategory != Done ORDER BY created DESC
    """
    client = get_jira_client_singleton()
    try:
        data = client.search_issues(jql=jql, max_results=max_results, start_at=start_at)
    except requests.RequestException as e:
        raise RuntimeError(f"Jira search_issues failed: {e}") from e

    issues: List[Dict[str, Any]] = []
    for issue in data.get("issues", []):
        fields_data = issue.get("fields") or {}
        issues.append(
            {
                "key": issue.get("key"),
                "id": issue.get("id"),
                "summary": fields_data.get("summary"),
                "status": (fields_data.get("status") or {}).get("name"),
                "issuetype": (fields_data.get("issuetype") or {}).get("name"),
                "project_key": ((fields_data.get("project") or {}).get("key")),
                "assignee": (fields_data.get("assignee") or {}).get("displayName"),
            }
        )

    return {
        "total": data.get("total"),
        "max_results": data.get("maxResults"),
        "start_at": data.get("startAt"),
        "issues": issues,
        "raw": data,
    }


@mcp.tool()
def jira_create_issue(
    project_key: str,
    issue_type: str,
    summary: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create Jira issue.

    WARNING: this actually creates issues in Jira Server/DC.
    """
    client = get_jira_client_singleton()
    try:
        data = client.create_issue(
            project_key=project_key,
            issue_type=issue_type,
            summary=summary,
            description=description,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Jira create_issue failed: {e}") from e

    return {
        "key": data.get("key"),
        "id": data.get("id"),
        "self": data.get("self"),
        "raw": data,
    }


@mcp.tool()
def jira_delete_issue(issue_key: str, delete_subtasks: bool = False) -> Dict[str, Any]:
    """
    Delete Jira issue by key (Jira Server/DC 8.8.0).

    WARNING: this actually deletes issues in Jira Server/DC.
    """
    client = get_jira_client_singleton()
    try:
        client.delete_issue(issue_key=issue_key, delete_subtasks=delete_subtasks)
    except requests.RequestException as e:
        raise RuntimeError(f"Jira delete_issue failed: {e}") from e

    return {
        "key": issue_key,
        "deleted": True,
        "delete_subtasks": delete_subtasks,
    }


# --------------------------------------------------------------------
#  STDIO transport entrypoint (for Cursor / Claude / etc.)
# --------------------------------------------------------------------


if __name__ == "__main__":
    mcp.run(transport="stdio")
