from github import Github, GithubException

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


def get_github_client() -> Github:
    return Github(settings.github_token)


def parse_pr_number_from_ref(ref: str) -> int | None:
    """Extract PR number from a GitHub ref string like 'refs/pull/42/head'."""
    parts = ref.split("/")
    if len(parts) >= 3 and parts[1] == "pull":
        try:
            return int(parts[2])
        except ValueError:
            pass
    return None
