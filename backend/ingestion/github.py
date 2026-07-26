from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from git import Repo

_GITHUB_PATTERN = re.compile(r"^/(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+?)(?:\.git)?/?$")


@dataclass(frozen=True)
class GitHubRepository:
    url: str
    owner: str
    name: str

    @property
    def id(self) -> str:
        token = hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:12]
        return f"{self.owner.lower()}-{self.name.lower()}-{token}"


def parse_public_github_url(url: str) -> GitHubRepository:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("Only public https://github.com/owner/repository URLs are supported.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use a clean public GitHub repository URL without credentials or query parameters.")
    match = _GITHUB_PATTERN.match(parsed.path)
    if not match:
        raise ValueError("Repository URL must have exactly an owner and repository name.")
    owner, name = match.group("owner"), match.group("name")
    canonical_url = f"https://github.com/{owner}/{name}.git"
    return GitHubRepository(url=canonical_url, owner=owner, name=name)


def clone_repository(repository: GitHubRepository, target: Path) -> str | None:
    """Clone the configured public repository into a controlled application directory."""
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    cloned = Repo.clone_from(repository.url, target, depth=1, multi_options=["--no-tags"])
    try:
        return cloned.active_branch.name
    except TypeError:
        return None
