"""Git service for repository operations."""
import re
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from git import (
    Actor,
    GitCommandError,
    Repo,
)

from app.config import settings


@dataclass
class GitInfo:
    """Git repository information."""

    commit_hash: str
    commit_message: str
    author: str
    branch: str


class GitError(Exception):
    """Git operation error."""

    pass


class GitService:
    """Service for Git operations."""

    def __init__(self, git_url: str, token: str | None = None) -> None:
        """Initialize Git service.

        Args:
            git_url: Git repository URL
            token: Optional Git access token for private repositories
        """
        self.git_url = git_url
        self.token = token
        self.repo: Repo | None = None
        self.repo_path: Path | None = None

    def _get_authenticated_url(self) -> str:
        """Get authenticated URL with token if available.

        Returns:
            Authenticated Git URL
        """
        if not self.token:
            return self.git_url

        # If URL already contains token, return as is
        if "://@" in self.git_url or "://oauth2:" in self.git_url:
            return self.git_url

        # Parse URL and insert token
        # Support formats:
        # - https://github.com/user/repo.git
        # - git@github.com:user/repo.git (SSH, token doesn't apply)
        # - https://user@github.com/user/repo.git

        if self.git_url.startswith("https://"):
            # Check if username already present
            if "://" in self.git_url and "@" in self.git_url.split("://")[1]:
                # Already has username, replace it
                base_url = self.git_url.split("//")[0]
                rest = self.git_url.split("//")[1]
                if "/" in rest:
                    _, repo_path = rest.split("/", 1)
                    return f"{base_url}//oauth2:{self.token}@{repo_path}"
            return self.git_url.replace("https://", f"https://oauth2:{self.token}@")

        # For SSH URLs, token is not applicable
        return self.git_url

    def clone(self, target_dir: Path | None = None) -> Path:
        """Clone a Git repository.

        Args:
            target_dir: Target directory for cloning

        Returns:
            Path to cloned repository

        Raises:
            GitError: If clone operation fails
        """
        if target_dir is None:
            # Create a temp directory in work dir
            work_path = Path(settings.work_dir)
            work_path.mkdir(parents=True, exist_ok=True)
            target_dir = work_path / f"repo_{id(self)}"

        try:
            url = self._get_authenticated_url()
            self.repo_path = Path(
                Repo.clone_from(url, target_dir, depth=1).working_dir
            )
            self.repo = Repo(self.repo_path)
            return self.repo_path
        except GitCommandError as e:
            raise GitError(f"Failed to clone repository: {e}") from e

    def checkout_branch(self, branch_name: str) -> None:
        """Checkout a branch.

        Args:
            branch_name: Name of the branch to checkout

        Raises:
            GitError: If checkout operation fails
        """
        if not self.repo:
            raise GitError("Repository not initialized. Call clone() first.")

        try:
            # Fetch remote branches with authenticated URL
            url = self._get_authenticated_url()
            if url != self.git_url:
                # Update remote URL if using token
                self.repo.remotes.origin.set_url(url)

            # Fetch remote branches
            self.repo.remotes.origin.fetch()

            # Checkout branch
            self.repo.remotes.origin.fetch(branch_name)
            self.repo.git.checkout(branch_name)

            # Pull latest changes
            self.repo.remotes.origin.pull()
        except GitCommandError as e:
            raise GitError(f"Failed to checkout branch '{branch_name}': {e}") from e

    def pull_latest(self) -> None:
        """Pull latest changes from remote.

        Raises:
            GitError: If pull operation fails
        """
        if not self.repo:
            raise GitError("Repository not initialized. Call clone() first.")

        try:
            # Update remote URL if using token
            url = self._get_authenticated_url()
            if url != self.git_url:
                self.repo.remotes.origin.set_url(url)

            self.repo.remotes.origin.pull()
        except GitCommandError as e:
            raise GitError(f"Failed to pull latest changes: {e}") from e

    def get_info(self) -> GitInfo:
        """Get current repository information.

        Returns:
            Git information

        Raises:
            GitError: If failed to get repository info
        """
        if not self.repo:
            raise GitError("Repository not initialized. Call clone() first.")

        try:
            head_commit = self.repo.head.commit
            branch = self.repo.active_branch.name

            return GitInfo(
                commit_hash=head_commit.hexsha,
                commit_message=head_commit.message.strip(),
                author=str(head_commit.author),
                branch=branch,
            )
        except GitCommandError as e:
            raise GitError(f"Failed to get repository info: {e}") from e

    def get_branches(self) -> list[str]:
        """Get list of all branches.

        Returns:
            List of branch names

        Raises:
            GitError: If failed to get branches
        """
        if not self.repo:
            raise GitError("Repository not initialized. Call clone() first.")

        try:
            # Fetch all remote branches
            self.repo.remotes.origin.fetch()

            branches = []
            for ref in self.repo.references:
                name = ref.name
                # Extract branch name from refs/heads/ or refs/remotes/origin/
                if name.startswith("refs/heads/"):
                    branches.append(name.replace("refs/heads/", ""))
                elif name.startswith("refs/remotes/origin/"):
                    branch_name = name.replace("refs/remotes/origin/", "")
                    # Skip HEAD reference
                    if branch_name != "HEAD":
                        branches.append(branch_name)

            # Remove duplicates and sort
            return sorted(set(branches))
        except GitCommandError as e:
            raise GitError(f"Failed to get branches: {e}") from e

    def cleanup(self) -> None:
        """Clean up the cloned repository."""
        if self.repo_path and self.repo_path.exists():
            shutil.rmtree(self.repo_path, ignore_errors=True)
            self.repo_path = None
            self.repo = None

    def __enter__(self) -> "GitService":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit."""
        self.cleanup()


@contextmanager
def git_context(git_url: str, branch: str, token: str | None = None) -> Generator[GitService, None, None]:
    """Context manager for Git operations.

    Args:
        git_url: Git repository URL
        branch: Branch to checkout
        token: Optional Git access token for private repositories

    Yields:
        Git service instance
    """
    service = GitService(git_url, token)
    try:
        service.clone()
        service.checkout_branch(branch)
        yield service
    finally:
        service.cleanup()


def get_remote_branches(git_url: str, token: str | None = None) -> list[str]:
    """Get list of remote branches without cloning.

    Args:
        git_url: Git repository URL
        token: Optional Git access token for private repositories

    Returns:
        List of branch names

    Raises:
        GitError: If failed to get branches
    """
    service = GitService(git_url, token)
    try:
        service.clone()
        return service.get_branches()
    finally:
        service.cleanup()
