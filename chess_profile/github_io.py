"""Talking to GitHub issues. The game logic only sees the IssueClient interface."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple


@dataclass(frozen=True)
class OpenIssue:
    number: int
    title: str
    created_at: str


class IssueClient(Protocol):
    def comment(self, number: int, body: str) -> None: ...

    def close(self, number: int, reason: str = "completed") -> None:
        """reason: "completed" or "not_planned"."""
        ...

    def create_issue(self, title: str, body: str) -> int: ...

    def open_issues(self) -> List[OpenIssue]: ...


class GitHubIssueClient:
    """Uses the REST API with the workflow's GITHUB_TOKEN. Standard library only."""

    def __init__(self, repo: str, token: str) -> None:
        self._base = f"https://api.github.com/repos/{repo}"
        self._token = token

    def comment(self, number: int, body: str) -> None:
        self._request("POST", f"/issues/{number}/comments", {"body": body})

    def close(self, number: int, reason: str = "completed") -> None:
        self._request("PATCH", f"/issues/{number}", {"state": "closed", "state_reason": reason})

    def create_issue(self, title: str, body: str) -> int:
        return int(self._request("POST", "/issues", {"title": title, "body": body})["number"])

    def open_issues(self) -> List[OpenIssue]:
        items = self._request("GET", "/issues?state=open&per_page=100")
        return [
            OpenIssue(number=i["number"], title=i["title"], created_at=i["created_at"])
            for i in items
            if "pull_request" not in i
        ]

    def _request(self, method: str, path: str, payload: Optional[dict] = None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self._base + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else None


class ConsoleIssueClient:
    """Prints instead of calling GitHub, and keeps a log. Used for dry runs, local play and tests."""

    def __init__(self, echo: bool = True, issues: Optional[List[OpenIssue]] = None) -> None:
        self.calls: List[Tuple] = []
        self._echo = echo
        self._next_number = 9000
        self._issues = list(issues or [])

    def comment(self, number: int, body: str) -> None:
        self._log(("comment", number, body), f"[comment on #{number}]\n{body}")

    def close(self, number: int, reason: str = "completed") -> None:
        self._log(("close", number, reason), f"[close #{number} as {reason}]")

    def create_issue(self, title: str, body: str) -> int:
        self._next_number += 1
        self._log(("create", self._next_number, title), f"[create issue #{self._next_number}: {title}]")
        return self._next_number

    def open_issues(self) -> List[OpenIssue]:
        return list(self._issues)

    def _log(self, call: Tuple, text: str) -> None:
        self.calls.append(call)
        if self._echo:
            print(text)
