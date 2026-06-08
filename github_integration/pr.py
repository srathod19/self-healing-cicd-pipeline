import os
import base64
from github import Github, GithubException

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
BOT_BRANCH_PREFIX = "self-heal"


def create_pr(repo: str, branch: str, patch: str, patch_file: str, reasoning: str, run_id: str) -> str:
    """
    Create a new branch with the patch applied, then open a PR.
    Returns the PR URL.
    """
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN not set")
    if not patch or not patch_file:
        raise ValueError("No patch to apply")

    g = Github(GITHUB_TOKEN)
    gh_repo = g.get_repo(repo)

    base_ref = gh_repo.get_branch(branch)
    base_sha = base_ref.commit.sha

    fix_branch = f"{BOT_BRANCH_PREFIX}/{run_id[:8]}"

    try:
        gh_repo.create_git_ref(ref=f"refs/heads/{fix_branch}", sha=base_sha)
    except GithubException as e:
        if e.status != 422:
            raise

    try:
        existing = gh_repo.get_contents(patch_file, ref=branch)
        current_content = base64.b64decode(existing.content).decode()
        new_content = apply_unified_diff(current_content, patch)
        gh_repo.update_file(
            path=patch_file,
            message=f"fix(agent): auto-patch for run {run_id[:8]}",
            content=new_content,
            sha=existing.sha,
            branch=fix_branch,
        )
    except Exception as e:
        gh_repo.create_file(
            path=patch_file,
            message=f"fix(agent): auto-patch for run {run_id[:8]}",
            content=patch,
            branch=fix_branch,
        )

    pr = gh_repo.create_pull(
        title=f"[self-heal] Auto-fix for failed run {run_id[:8]}",
        body=(
            f"## Auto-generated fix\n\n"
            f"**Run ID:** `{run_id}`\n"
            f"**Source branch:** `{branch}`\n\n"
            f"### Agent reasoning\n{reasoning}\n\n"
            f"### Patch applied\n```\n{patch}\n```\n\n"
            f"> This PR was opened automatically by the self-healing CI/CD agent. "
            f"Please review before merging."
        ),
        head=fix_branch,
        base=branch,
    )
    return pr.html_url


def apply_unified_diff(original: str, diff: str) -> str:
    """
    Naively apply a unified diff to file content.
    For production, use the `patch` CLI or `whatthepatch` library.
    """
    lines = original.splitlines(keepends=True)
    result = []
    for line in diff.splitlines(keepends=True):
        if line.startswith("+") and not line.startswith("+++"):
            result.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            pass
        elif not line.startswith(("@@", "---", "+++")):
            result.append(line)
    return "".join(result) if result else original
