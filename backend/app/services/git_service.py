"""Git service for repository operations."""
import os
import shutil
import tempfile
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

# Disable SSL verification for Git (for self-signed certificates)
os.environ['GIT_SSL_NO_VERIFY'] = '1'


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
    """Service for Git operations with SSH key or Token authentication."""

    def __init__(
        self,
        git_url: str,
        ssh_key: str | None = None,
        git_token: str | None = None,
    ) -> None:
        """Initialize Git service.

        Args:
            git_url: Git repository URL (SSH: git@github.com:user/repo.git or HTTPS: https://github.com/user/repo.git)
            ssh_key: Optional SSH private key for SSH private repositories
            git_token: Optional access token for HTTPS private repositories
        """
        self.original_git_url = git_url
        self.ssh_key = ssh_key
        self.git_token = git_token
        self.repo: Repo | None = None
        self.repo_path: Path | None = None
        self._ssh_key_file: Path | None = None
        self._credential_file: Path | None = None
        self._askpass_file: Path | None = None

        # For HTTPS with token, don't embed in URL - use credential helper instead
        self.git_url = git_url

    def _is_ssh_url(self) -> bool:
        """Check if the URL is an SSH URL.

        Returns:
            True if URL uses SSH protocol
        """
        return (
            self.original_git_url.startswith('git@') or
            self.original_git_url.startswith('ssh://') or
            (':' in self.original_git_url and not self.original_git_url.startswith('http'))
        )

    def _setup_auth(self) -> dict:
        """Setup authentication for Git operations (SSH key or Token).

        Returns:
            Environment variables dict for Git operations
        """
        env = {'GIT_SSL_NO_VERIFY': '1'}

        # For HTTPS with token, setup credential helper
        if self.git_token and not self._is_ssh_url():
            return self._setup_token_credential(env)

        # For SSH URLs, setup SSH key
        if self._is_ssh_url():
            return self._setup_ssh_key(env)

        return env

    def _setup_token_credential(self, env: dict) -> dict:
        """Setup Git credential helper for token authentication.

        Args:
            env: Base environment variables

        Returns:
            Environment variables with credential helper configured
        """
        from urllib.parse import urlparse

        parsed = urlparse(self.git_url)
        credential_dir = Path(tempfile.gettempdir()) / "devops_git_credentials"
        credential_dir.mkdir(parents=True, exist_ok=True)

        # Create a unique credential helper script
        self._credential_file = credential_dir / f"cred_helper_{id(self)}"

        # Write git credential helper script (not GIT_ASKPASS)
        script_content = f'''#!/bin/bash
# Git credential helper for token authentication
if [ "$1" = "get" ]; then
    echo "protocol={parsed.scheme}"
    echo "host={parsed.netloc}"
    echo "path={parsed.path}"
    echo "username={self.git_token}"
    echo "password="
    echo ""
elif [ "$1" = "store" ] || [ "$1" = "erase" ]; then
    # Do nothing - we don't store credentials
    echo ""
fi
'''
        self._credential_file.write_text(script_content)
        self._credential_file.chmod(0o700)

        # Use GIT_ASKPASS with a simpler script that outputs credentials
        askpass_file = credential_dir / f"askpass_{id(self)}"
        askpass_content = f'''#!/bin/bash
echo "{self.git_token}"
'''
        askpass_file.write_text(askpass_content)
        askpass_file.chmod(0o700)
        self._askpass_file = askpass_file

        env['GIT_ASKPASS'] = str(askpass_file)
        env['GIT_TERMINAL_PROMPT'] = '0'

        return env

    def _setup_ssh_key(self, env: dict) -> dict:
        """Setup SSH key for Git operations.

        Args:
            env: Base environment variables

        Returns:
            Environment variables with SSH configuration
        """

        # Create temporary SSH key file
        ssh_key_dir = Path(tempfile.gettempdir()) / "devops_ssh_keys"
        ssh_key_dir.mkdir(parents=True, exist_ok=True)

        # Create a unique key file
        key_file = ssh_key_dir / f"key_{id(self)}"
        key_file.write_text(self.ssh_key)
        key_file.chmod(0o600)

        self._ssh_key_file = key_file

        return {
            'GIT_SSL_NO_VERIFY': '1',
            'GIT_SSH_COMMAND': f'ssh -i {key_file} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
        }

    def _cleanup_ssh_key(self) -> None:
        """Clean up temporary SSH key file."""
        if self._ssh_key_file and self._ssh_key_file.exists():
            try:
                self._ssh_key_file.unlink()
            except Exception:
                pass
            self._ssh_key_file = None

    def _cleanup_credential_file(self) -> None:
        """Clean up temporary credential file."""
        if self._credential_file and self._credential_file.exists():
            try:
                self._credential_file.unlink()
            except Exception:
                pass
            self._credential_file = None

        if self._askpass_file and self._askpass_file.exists():
            try:
                self._askpass_file.unlink()
            except Exception:
                pass
            self._askpass_file = None

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

        # Clean up existing directory if present
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)

        try:
            # Setup authentication
            env = self._setup_auth()

            # Clone repository
            import git
            git.cmd.Git.GIT_PYTHON_TRACE = 'full'  # Enable full tracing for debugging

            self.repo_path = Path(
                Repo.clone_from(
                    self.git_url,
                    target_dir,
                    depth=1,
                    env=env
                ).working_dir
            )
            self.repo = Repo(self.repo_path)
            return self.repo_path
        except GitCommandError as e:
            # Provide detailed error information
            error_msg = f"Failed to clone repository from {self.git_url}"
            stderr = str(e.stderr).lower() if e.stderr else ""

            if "authentication" in stderr or "permission" in stderr:
                error_msg += " - Authentication failed. Please check your SSH key."
            elif "ssh" in stderr and "publickey" in stderr:
                error_msg += " - SSH key rejected. Make sure the SSH key is added to your Git account."
            elif "not found" in stderr or "does not exist" in stderr:
                error_msg += " - Repository not found. Please check the URL."
            elif "host key" in stderr:
                error_msg += " - SSH host key verification failed."
            else:
                error_msg += f" - {e}"

            raise GitError(error_msg) from e
        finally:
            # Clean up credential file after clone
            self._cleanup_credential_file()
            # Clean up SSH key file after clone
            self._cleanup_ssh_key()

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
            # Setup authentication for remote operations
            env = self._setup_auth()

            # Fetch all remote branches
            self.repo.git.fetch(env=env)

            # Try to find the remote branch
            remote_branch = f"origin/{branch_name}"
            remote_refs = [ref.name for ref in self.repo.references]

            # Check if remote branch exists
            if f"refs/remotes/{remote_branch}" not in remote_refs:
                raise GitError(
                    f"Branch '{branch_name}' not found in remote repository"
                )

            # Create local branch tracking remote branch
            try:
                # Check if local branch already exists
                self.repo.heads[branch_name]
                # Local branch exists, just checkout
                self.repo.git.checkout(branch_name)
            except (IndexError, GitCommandError):
                # Local branch doesn't exist, create new tracking branch
                self.repo.git.checkout(f"{remote_branch}", b=branch_name)

            # Pull latest changes
            self.repo.remotes.origin.pull(env=env)
        except GitCommandError as e:
            raise GitError(f"Failed to checkout branch '{branch_name}': {e}") from e
        finally:
            # Clean up credential file
            self._cleanup_credential_file()
            # Clean up SSH key file
            self._cleanup_ssh_key()

    def pull_latest(self) -> None:
        """Pull latest changes from remote.

        Raises:
            GitError: If pull operation fails
        """
        if not self.repo:
            raise GitError("Repository not initialized. Call clone() first.")

        try:
            # Setup authentication for remote operations
            env = self._setup_auth()
            self.repo.remotes.origin.pull(env=env)
        except GitCommandError as e:
            raise GitError(f"Failed to pull latest changes: {e}") from e
        finally:
            # Clean up credential file
            self._cleanup_credential_file()
            # Clean up SSH key file
            self._cleanup_ssh_key()

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
            # Setup authentication for remote operations
            env = self._setup_auth()

            # Fetch all remote branches
            self.repo.remotes.origin.fetch(env=env)

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
        finally:
            # Clean up credential file
            self._cleanup_credential_file()
            # Clean up SSH key file
            self._cleanup_ssh_key()

    def cleanup(self) -> None:
        """Clean up the cloned repository and credentials."""
        if self.repo_path and self.repo_path.exists():
            shutil.rmtree(self.repo_path, ignore_errors=True)
            self.repo_path = None
            self.repo = None

        # Clean up credential file
        self._cleanup_credential_file()
        # Clean up SSH key file
        self._cleanup_ssh_key()

    def __enter__(self) -> "GitService":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit."""
        self.cleanup()


@contextmanager
def git_context(
    git_url: str,
    branch: str,
    ssh_key: str | None = None,
    git_token: str | None = None,
) -> Generator[GitService, None, None]:
    """Context manager for Git operations.

    Args:
        git_url: Git repository URL (SSH or HTTPS format)
        branch: Branch to checkout
        ssh_key: Optional SSH private key for SSH private repositories
        git_token: Optional access token for HTTPS private repositories

    Yields:
        Git service instance
    """
    service = GitService(git_url, ssh_key=ssh_key, git_token=git_token)
    try:
        service.clone()
        service.checkout_branch(branch)
        yield service
    finally:
        service.cleanup()


def get_remote_branches(
    git_url: str,
    ssh_key: str | None = None,
    git_token: str | None = None,
) -> list[str]:
    """Get list of remote branches without cloning.

    Args:
        git_url: Git repository URL (SSH or HTTPS format)
        ssh_key: Optional SSH private key for SSH private repositories
        git_token: Optional access token for HTTPS private repositories

    Returns:
        List of branch names

    Raises:
        GitError: If failed to get branches
    """
    service = GitService(git_url, ssh_key=ssh_key, git_token=git_token)
    try:
        service.clone()
        return service.get_branches()
    finally:
        service.cleanup()
