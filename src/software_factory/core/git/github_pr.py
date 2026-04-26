"""GitHub pull request client and payload helpers."""

from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class PullRequestRef:
    """Minimal pull request identifier."""

    number: int
    url: str


class GitHubPRClient:
    """Thin GitHub pull-request API wrapper."""

    def __init__(
        self,
        token: str | None,
        api_base_url: str = "https://api.github.com",
        dry_run: bool = False,
        session: requests.Session | None = None,
    ):
        self.token = token
        self.api_base_url = api_base_url.rstrip("/")
        self.dry_run = dry_run or token is None
        self.session = session or requests.Session()

    def create_or_update_pull_request(
        self,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str,
        existing_number: int | None = None,
    ) -> PullRequestRef:
        """Create or update a pull request for a branch."""

        if self.dry_run:
            fake_number = existing_number or 0
            fake_url = f"https://github.com/{repo}/pull/{fake_number or 'dry-run'}"
            return PullRequestRef(number=fake_number, url=fake_url)

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if existing_number is None:
            response = self.session.post(
                f"{self.api_base_url}/repos/{repo}/pulls",
                headers=headers,
                json={"title": title, "head": head, "base": base, "body": body},
                timeout=30,
            )
        else:
            response = self.session.patch(
                f"{self.api_base_url}/repos/{repo}/pulls/{existing_number}",
                headers=headers,
                json={"title": title, "body": body, "base": base},
                timeout=30,
            )

        response.raise_for_status()
        payload = response.json()
        return PullRequestRef(number=int(payload["number"]), url=str(payload["html_url"]))


def build_pr_body(ticket_id: str, run_id: str, acceptance_criteria: list[str], evidence: dict[str, str]) -> str:
    """Build a structured PR body containing run and evidence metadata."""

    criteria_lines = "\n".join(f"- [x] {item}" for item in acceptance_criteria)
    evidence_lines = "\n".join(f"- `{name}`: {uri}" for name, uri in evidence.items())
    return (
        f"## Automated Change\n"
        f"- Ticket: `{ticket_id}`\n"
        f"- Run: `{run_id}`\n\n"
        f"## Acceptance Criteria\n{criteria_lines or '- [ ] (not provided)'}\n\n"
        f"## Evidence\n{evidence_lines or '- none'}\n"
    )
