def review_key(repo: str, pr_number: int) -> str:
    return f"review:{repo}:{pr_number}"


def pr_diff_key(repo: str, sha: str) -> str:
    return f"diff:{repo}:{sha}"


def github_file_key(repo: str, file_path: str, commit_sha: str) -> str:
    return f"github:file:{repo}:{file_path}:{commit_sha}"


def rate_limit_key(repo: str) -> str:
    return f"rate_limit:{repo}"


def repo_profile_key(repo_id: str) -> str:
    return f"repo:profile:{repo_id}"
