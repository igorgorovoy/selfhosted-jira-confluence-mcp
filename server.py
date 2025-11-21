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

    def create_space(
        self,
        key: str,
        name: str,
        description: Optional[str] = None,
        space_type: str = "global",
    ) -> Dict[str, Any]:
        """
        Create a Confluence space.

        Wrapper around POST /rest/api/space.
        """
        payload: Dict[str, Any] = {
            "key": key,
            "name": name,
            "type": space_type,
        }
        if description:
            payload["description"] = {
                "plain": {
                    "value": description,
                    "representation": "plain",
                }
            }

        resp = self.session.post(self._url("/space"), json=payload)
        resp.raise_for_status()
        return resp.json()

    def delete_page(self, page_id: str, status: str = "current") -> None:
        """
        Delete a Confluence page by ID.

        By default deletes the current version. Confluence may return 204 No Content on success.
        """
        resp = self.session.delete(self._url(f"/content/{page_id}"), params={"status": status})
        resp.raise_for_status()

    def delete_space(self, key: str) -> None:
        """
        Delete a Confluence space by key.

        Wrapper around DELETE /rest/api/space/{spaceKey}.
        """
        resp = self.session.delete(self._url(f"/space/{key}"))
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
        extra_fields: Optional[Dict[str, Any]] = None,
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

        if extra_fields:
            # Користувач може передати будь-які додаткові поля Jira (у т.ч. customfield_*).
            # Значення з extra_fields перекривають базові, якщо ключі збігаються.
            payload["fields"].update(extra_fields)

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

    def get_createmeta(
        self,
        project_key: str,
        issue_type_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch create metadata for a project/issue type.

        Wrapper around /rest/api/2/issue/createmeta with fields expansion so we can
        see which fields are required and what allowed values they have.
        """
        params: Dict[str, Any] = {
            "projectKeys": project_key,
            "expand": "projects.issuetypes.fields",
        }
        if issue_type_name:
            params["issuetypeNames"] = issue_type_name

        resp = self.session.get(self._url("/issue/createmeta"), params=params)
        resp.raise_for_status()
        return resp.json()

    def create_project(
        self,
        key: str,
        name: str,
        project_type_key: str,
        lead: str,
        description: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create Jira project (Server/DC 8.8.0).

        Minimal wrapper around POST /rest/api/2/project. The caller is responsible
        for passing a valid combination of type/template/lead according to Jira settings.
        """
        payload: Dict[str, Any] = {
            "key": key,
            "name": name,
            "projectTypeKey": project_type_key,
            "lead": lead,
        }
        if description:
            payload["description"] = description
        if extra_fields:
            payload.update(extra_fields)

        resp = self.session.post(self._url("/project"), json=payload)
        resp.raise_for_status()
        return resp.json()

    def delete_project(self, key: str) -> None:
        """
        Delete Jira project by key (or ID).

        Wrapper around DELETE /rest/api/2/project/{projectIdOrKey}.
        Jira typically returns 202 Accepted with an empty body.
        """
        resp = self.session.delete(self._url(f"/project/{key}"))
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
def confluence_create_space(
    key: str,
    name: str,
    description: Optional[str] = None,
    space_type: str = "global",
) -> Dict[str, Any]:
    """
    Create a Confluence space.

    WARNING: this actually creates a space in Confluence.
    """
    client = get_confluence_client_singleton()
    try:
        data = client.create_space(
            key=key,
            name=name,
            description=description,
            space_type=space_type,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Confluence create_space failed: {e}") from e

    return {
        "key": data.get("key"),
        "name": data.get("name"),
        "type": data.get("type"),
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


@mcp.tool()
def confluence_delete_space(key: str) -> Dict[str, Any]:
    """
    Delete a Confluence space by key.

    WARNING: this actually deletes a space in Confluence. Depending on configuration,
    it may be moved to trash or removed permanently.
    """
    client = get_confluence_client_singleton()
    try:
        client.delete_space(key=key)
    except requests.RequestException as e:
        raise RuntimeError(f"Confluence delete_space failed: {e}") from e

    return {
        "key": key,
        "deleted": True,
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
     extra_fields: Optional[Dict[str, Any]] = None,
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
            extra_fields=extra_fields,
        )
    except requests.HTTPError as e:
        # Спробуємо дістати детальну інформацію від Jira (errorMessages/errors),
        # щоб у чаті було видно, яких саме полів не вистачає.
        detail = ""
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                err_json = resp.json()
                detail = f" | Jira response: {err_json}"
            except ValueError:
                # Відповідь не JSON
                text = resp.text.strip()
                if text:
                    detail = f" | Jira raw response: {text}"
        raise RuntimeError(f"Jira create_issue failed: {e}{detail}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"Jira create_issue failed: {e}") from e

    return {
        "key": data.get("key"),
        "id": data.get("id"),
        "self": data.get("self"),
        "raw": data,
    }


@mcp.tool()
def jira_create_project(
    key: str,
    name: str,
    project_type_key: str,
    lead: str,
    description: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create Jira project.

    WARNING: this actually creates a project in Jira Server/DC.
    """
    client = get_jira_client_singleton()
    try:
        data = client.create_project(
            key=key,
            name=name,
            project_type_key=project_type_key,
            lead=lead,
            description=description,
            extra_fields=extra_fields,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Jira create_project failed: {e}") from e

    return {
        "key": data.get("key"),
        "id": data.get("id"),
        "self": data.get("self"),
        "raw": data,
    }


@mcp.tool()
def jira_create_issue_debug(
    project_key: str,
    issue_type: str,
    summary: str,
    description: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Debug helper for Jira issue creation.

    Sends the same payload as jira_create_issue but does NOT raise on non-2xx responses.
    Returns HTTP status code, request payload and parsed response body (if any).
    """
    client = get_jira_client_singleton()

    payload: Dict[str, Any] = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
    }
    if description:
        payload["fields"]["description"] = description
    if extra_fields:
        payload["fields"].update(extra_fields)

    resp = client.session.post(client._url("/issue"), json=payload)  # type: ignore[attr-defined]

    try:
        body = resp.json()
    except ValueError:
        body = {"raw_text": resp.text}

    return {
        "status_code": resp.status_code,
        "ok": resp.ok,
        "request_payload": payload,
        "response_body": body,
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


@mcp.tool()
def jira_delete_project(key: str) -> Dict[str, Any]:
    """
    Delete Jira project by key (or ID).

    WARNING: this actually deletes projects in Jira Server/DC.
    """
    client = get_jira_client_singleton()
    try:
        client.delete_project(key=key)
    except requests.RequestException as e:
        raise RuntimeError(f"Jira delete_project failed: {e}") from e

    return {
        "key": key,
        "deleted": True,
    }


@mcp.tool()
def jira_get_createmeta(
    project_key: str,
    issue_type_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get Jira create metadata for a project / issue type.

    Useful to discover which fields are required when creating issues,
    and what allowed values they can take.
    """
    client = get_jira_client_singleton()
    try:
        data = client.get_createmeta(project_key=project_key, issue_type_name=issue_type_name)
    except requests.RequestException as e:
        raise RuntimeError(f"Jira get_createmeta failed: {e}") from e

    # Build a simplified view of fields for easier inspection in chat.
    simplified_projects: List[Dict[str, Any]] = []
    for project in data.get("projects", []):
        simple_project: Dict[str, Any] = {
            "key": project.get("key"),
            "id": project.get("id"),
            "name": project.get("name"),
            "issuetypes": [],
        }
        for itype in project.get("issuetypes", []):
            fields = itype.get("fields") or {}
            simple_fields: List[Dict[str, Any]] = []
            for field_id, field_def in fields.items():
                simple_fields.append(
                    {
                        "id": field_id,
                        "name": field_def.get("name"),
                        "required": field_def.get("required"),
                        "schema": field_def.get("schema"),
                        "allowed_values_sample": (field_def.get("allowedValues") or [None])[0],
                    }
                )
            simple_project["issuetypes"].append(
                {
                    "id": itype.get("id"),
                    "name": itype.get("name"),
                    "fields": simple_fields,
                }
            )
        simplified_projects.append(simple_project)

    return {
        "projects": simplified_projects,
        "raw": data,
    }


# --------------------------------------------------------------------
#  STDIO transport entrypoint (for Cursor / Claude / etc.)
# --------------------------------------------------------------------


if __name__ == "__main__":
    mcp.run(transport="stdio")
