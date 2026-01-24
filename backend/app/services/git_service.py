"""Git service for repository operations."""
import asyncio
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Generator

from git import (
    Actor,
    GitCommandError,
    Repo,
)

from app.config import settings

if TYPE_CHECKING:
    from app.services.log_service import DeploymentLogger

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
        logger: "DeploymentLogger | None" = None,
    ) -> None:
        """Initialize Git service.

        Args:
            git_url: Git repository URL (SSH: git@github.com:user/repo.git or HTTPS: https://github.com/user/repo.git)
            ssh_key: Optional SSH private key for SSH private repositories
            git_token: Optional access token for HTTPS private repositories
            logger: Optional DeploymentLogger for logging operations
        """
        self.original_git_url = git_url
        self.ssh_key = ssh_key
        self.git_token = git_token
        self.logger = logger
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

    def _log_info(self, message: str) -> None:
        """Log info message (synchronous wrapper for async logger).

        Args:
            message: Message to log
        """
        if self.logger:
            try:
                # Create new event loop if none exists
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        raise RuntimeError("Loop is closed")
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Run async logging in existing loop
                if loop.is_running():
                    # If loop is running, schedule the coroutine
                    asyncio.create_task(self.logger.info(message))
                else:
                    # If loop is not running, run the coroutine
                    loop.run_until_complete(self.logger.info(message))
            except Exception:
                # Silently fail if logging fails
                pass

    def _log_error(self, message: str) -> None:
        """Log error message (synchronous wrapper for async logger).

        Args:
            message: Message to log
        """
        if self.logger:
            try:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        raise RuntimeError("Loop is closed")
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    asyncio.create_task(self.logger.error(message))
                else:
                    loop.run_until_complete(self.logger.error(message))
            except Exception:
                pass

    def _log_warning(self, message: str) -> None:
        """Log warning message (synchronous wrapper for async logger).

        Args:
            message: Message to log
        """
        if self.logger:
            try:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        raise RuntimeError("Loop is closed")
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    asyncio.create_task(self.logger.warning(message))
                else:
                    loop.run_until_complete(self.logger.warning(message))
            except Exception:
                pass

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

        # Write git credential helper script
        script_content = f'''#!/bin/bash
# Git credential helper for token authentication
if [ "$1" = "get" ]; then
    echo "protocol={parsed.scheme}"
    echo "host={parsed.netloc}"
    echo "username=oauth2"
    echo "password={self.git_token}"
    echo ""
elif [ "$1" = "store" ] || [ "$1" = "erase" ]; then
    # Do nothing - we don't store credentials
    echo ""
fi
'''
        self._credential_file.write_text(script_content)
        self._credential_file.chmod(0o700)

        # Configure Git to use the credential helper
        env['GIT_ASKPASS'] = str(self._credential_file)
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

    def clone(self, target_dir: Path | None = None, branch: str | None = None) -> Path:
        """Clone a Git repository.

        Args:
            target_dir: Target directory for cloning
            branch: Optional branch to clone (fetches all branches if None)

        Returns:
            Path to cloned repository

        Raises:
            GitError: If clone operation fails
        """
        # Log clone start
        self._log_info("===== 开始克隆 Git 仓库 =====")
        self._log_info(f"仓库地址: {self.git_url}")
        self._log_info(f"指定分支: {branch if branch else '默认分支'}")

        if target_dir is None:
            # Create a temp directory in work dir
            work_path = Path(settings.work_dir)
            work_path.mkdir(parents=True, exist_ok=True)
            target_dir = work_path / f"repo_{id(self)}"

        self._log_info(f"目标目录: {target_dir}")

        # Clean up existing directory if present
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
            self._log_info("已清理已存在的目标目录")

        try:
            # Setup authentication
            env = self._setup_auth()

            # Clone repository
            import git
            git.cmd.Git.GIT_PYTHON_TRACE = 'full'  # Enable full tracing for debugging

            self._log_info("正在克隆仓库...")

            # Clone without --depth to get all remote branches
            # Use --single-branch only if a specific branch is requested
            clone_args = ["--no-tags"]
            if branch:
                clone_args.extend(["--single-branch", "--branch", branch])

            self.repo_path = Path(
                Repo.clone_from(
                    self.git_url,
                    target_dir,
                    env=env,
                    multi_options=clone_args
                ).working_dir
            )
            self.repo = Repo(self.repo_path)

            self._log_info("仓库克隆成功")

            # Get current branch and commit info
            try:
                current_branch = self.repo.active_branch.name
                self._log_info(f"当前分支: {current_branch}")

                head_commit = self.repo.head.commit
                commit_message = head_commit.message.strip()
                # Truncate long commit messages
                if len(commit_message) > 100:
                    commit_message = commit_message[:97] + "..."
                self._log_info(f"最新提交: {head_commit.hexsha[:7]} - {commit_message}")
            except Exception as e:
                self._log_warning(f"无法获取仓库信息: {e}")

            # Fetch all remote branches to ensure they're available for checkout
            try:
                self.repo.git.fetch(env=env, all=True, tags=False)
                self._log_info("已获取所有远程分支")
            except GitCommandError as e:
                # If fetch all fails, the initial clone should still work
                self._log_warning(f"获取远程分支失败（非致命错误）: {e}")

            # Note: Don't clean up credential/ssh files yet - they're needed for subsequent operations
            # They will be cleaned up in cleanup() or __exit__

            return self.repo_path
        except GitCommandError as e:
            # Provide detailed error information
            error_msg = f"Failed to clone repository from {self.git_url}"
            stderr = str(e.stderr).lower() if e.stderr else ""

            if "authentication" in stderr or "permission" in stderr:
                error_msg += " - Authentication failed. Please check your credentials."
            elif "ssh" in stderr and "publickey" in stderr:
                error_msg += " - SSH key rejected. Make sure the SSH key is added to your Git account."
            elif "not found" in stderr or "does not exist" in stderr:
                error_msg += " - Repository not found. Please check the URL."
            elif "host key" in stderr:
                error_msg += " - SSH host key verification failed."
            else:
                error_msg += f" - {e}"

            self._log_error(f"克隆失败: {error_msg}")
            raise GitError(error_msg) from e

    def checkout_branch(self, branch_name: str) -> None:
        """Checkout a branch.

        Args:
            branch_name: Name of the branch to checkout

        Raises:
            GitError: If checkout operation fails
        """
        if not self.repo:
            raise GitError("Repository not initialized. Call clone() first.")

        self._log_info(f"切换到分支: {branch_name}")

        try:
            # Setup authentication for remote operations
            env = self._setup_auth()

            # Fetch all remote branches with explicit parameters
            # Using --all to fetch all remotes and branches
            self._log_info("拉取最新代码...")
            try:
                self.repo.git.fetch(env=env, all=True, prune=True, tags=False)
                self._log_info("已获取所有远程分支")
            except GitCommandError as fetch_error:
                # If fetch fails, try without --all
                try:
                    self.repo.git.fetch(env=env, origin=branch_name, tags=False)
                    self._log_info(f"已获取分支 {branch_name}")
                except GitCommandError:
                    # If both fail, continue - the branch might already exist
                    self._log_warning(f"获取远程分支失败（尝试继续）: {fetch_error}")

            # List all available remote branches for debugging
            remote_refs = [ref.name for ref in self.repo.references]
            # Log all references for debugging
            self._log_info(f"所有引用: {remote_refs}")

            available_remote_branches = [
                name.replace("origin/", "")
                for name in remote_refs
                if name.startswith("origin/") and name != "origin/HEAD"
            ]

            # Check if the remote branch now exists
            remote_branch = f"origin/{branch_name}"

            # Check if remote branch exists
            if remote_branch not in remote_refs:
                self._log_error(
                    f"分支 '{branch_name}' 在远程仓库中不存在。"
                    f"可用远程分支: {', '.join(available_remote_branches) or '无'}"
                )
                raise GitError(
                    f"Branch '{branch_name}' not found in remote repository. "
                    f"Available remote branches: {', '.join(available_remote_branches) or 'none'}"
                )

            # Create local branch tracking remote branch
            try:
                # Check if local branch already exists
                self.repo.heads[branch_name]
                # Local branch exists, just checkout
                self.repo.git.checkout(branch_name)
                self._log_info(f"已切换到本地分支: {branch_name}")
            except (IndexError, GitCommandError):
                # Local branch doesn't exist, create new tracking branch
                # Use git checkout -b to create and track remote branch
                self.repo.git.checkout(remote_branch, b=branch_name)
                self._log_info(f"已创建本地分支 '{branch_name}' 并跟踪远程分支 '{remote_branch}'")

            # Pull latest changes
            try:
                pull_result = self.repo.remotes.origin.pull(env=env)
                # Check if there were any updates
                if pull_result and pull_result[0].flags > 0:
                    head_commit = self.repo.head.commit
                    commit_message = head_commit.message.strip()
                    if len(commit_message) > 100:
                        commit_message = commit_message[:97] + "..."
                    self._log_info(f"已更新到: {head_commit.hexsha[:7]} - {commit_message}")
                else:
                    self._log_info("已是最新版本")
            except GitCommandError as pull_error:
                self._log_warning(f"拉取最新代码时出现警告: {pull_error}")

        except GitCommandError as e:
            self._log_error(f"切换分支失败: {e}")
            raise GitError(f"Failed to checkout branch '{branch_name}': {e}") from e

    def pull_latest(self) -> None:
        """Pull latest changes from remote.

        Raises:
            GitError: If pull operation fails
        """
        if not self.repo:
            raise GitError("Repository not initialized. Call clone() first.")

        self._log_info("拉取最新代码...")

        try:
            # Setup authentication for remote operations
            env = self._setup_auth()

            # Get current commit before pull
            old_commit = self.repo.head.commit.hexsha[:7]

            pull_result = self.repo.remotes.origin.pull(env=env)

            # Get new commit after pull
            new_commit = self.repo.head.commit.hexsha[:7]

            if old_commit != new_commit:
                head_commit = self.repo.head.commit
                commit_message = head_commit.message.strip()
                if len(commit_message) > 100:
                    commit_message = commit_message[:97] + "..."
                self._log_info(f"已更新到: {new_commit} - {commit_message}")
            else:
                self._log_info("已是最新版本")
        except GitCommandError as e:
            self._log_error(f"拉取失败: {e}")
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

        self._log_info("获取分支列表...")

        try:
            # Setup authentication for remote operations
            env = self._setup_auth()

            # For shallow clones, use ls-remote to get all branch references from remote
            # This works even when local refs are incomplete due to shallow clone
            refs_output = self.repo.git.ls_remote('origin', heads=True, env=env)

            branches = []
            for line in refs_output.split('\n'):
                if not line.strip():
                    continue
                # ls-remote output format: <commit-hash>\trefs/heads/<branch-name>
                parts = line.split('\t')
                if len(parts) == 2 and parts[1].startswith('refs/heads/'):
                    branch_name = parts[1].replace('refs/heads/', '')
                    if branch_name:  # Skip empty branch names
                        branches.append(branch_name)

            # Sort branches
            return sorted(branches)
        except GitCommandError as e:
            self._log_error(f"获取分支列表失败: {e}")
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
    logger: "DeploymentLogger | None" = None,
) -> Generator[GitService, None, None]:
    """Context manager for Git operations.

    Args:
        git_url: Git repository URL (SSH or HTTPS format)
        branch: Branch to checkout
        ssh_key: Optional SSH private key for SSH private repositories
        git_token: Optional access token for HTTPS private repositories
        logger: Optional DeploymentLogger for logging operations

    Yields:
        Git service instance
    """
    service = GitService(git_url, ssh_key=ssh_key, git_token=git_token, logger=logger)
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
    logger: "DeploymentLogger | None" = None,
) -> list[str]:
    """Get list of remote branches without cloning.

    Args:
        git_url: Git repository URL (SSH or HTTPS format)
        ssh_key: Optional SSH private key for SSH private repositories
        git_token: Optional access token for HTTPS private repositories
        logger: Optional DeploymentLogger for logging operations

    Returns:
        List of branch names

    Raises:
        GitError: If failed to get branches
    """
    service = GitService(git_url, ssh_key=ssh_key, git_token=git_token, logger=logger)
    try:
        service.clone()
        return service.get_branches()
    finally:
        service.cleanup()
