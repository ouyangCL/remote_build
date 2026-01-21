"""Git service for repository operations."""
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

    def __init__(self, git_url: str) -> None:
        """Initialize Git service.

        Args:
            git_url: Git repository URL
        """
        self.git_url = git_url
        self.repo: Repo | None = None
        self.repo_path: Path | None = None

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
            self.repo_path = Path(
                Repo.clone_from(self.git_url, target_dir, depth=1).working_dir
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
def git_context(git_url: str, branch: str) -> Generator[GitService, None, None]:
    """Context manager for Git operations.

    Args:
        git_url: Git repository URL
        branch: Branch to checkout

    Yields:
        Git service instance
    """
    service = GitService(git_url)
    try:
        service.clone()
        service.checkout_branch(branch)
        yield service
    finally:
        service.cleanup()


def get_remote_branches(git_url: str) -> list[str]:
    """Get list of remote branches without cloning.

    Args:
        git_url: Git repository URL

    Returns:
        List of branch names

    Raises:
        GitError: If failed to get branches
    """
    service = GitService(git_url)
    try:
        service.clone()
        return service.get_branches()
    finally:
        service.cleanup()
