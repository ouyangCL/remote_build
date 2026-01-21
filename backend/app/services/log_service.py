"""Log service for deployment logs."""
import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from app.models.deployment import Deployment, DeploymentLog


class LogLevel(str, Enum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class LogEntry:
    """Log entry."""

    level: LogLevel
    content: str
    timestamp: datetime


class LogBuffer:
    """In-memory log buffer for real-time streaming."""

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize log buffer.

        Args:
            max_size: Maximum number of log entries to keep in memory
        """
        self.buffer: deque[LogEntry] = deque(maxlen=max_size)
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to log updates.

        Returns:
            Queue for receiving log updates
        """
        queue: asyncio.Queue[LogEntry] = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)

            # Send existing logs to new subscriber
            for entry in self.buffer:
                await queue.put(entry)

        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from log updates.

        Args:
            queue: Queue to unsubscribe
        """
        async with self._lock:
            self._subscribers.discard(queue)

    async def append(self, level: LogLevel, content: str) -> None:
        """Append a log entry.

        Args:
            level: Log level
            content: Log content
        """
        entry = LogEntry(
            level=level,
            content=content,
            timestamp=datetime.utcnow(),
        )

        self.buffer.append(entry)

        # Notify subscribers
        async with self._lock:
            for queue in self._subscribers:
                try:
                    await queue.put(entry)
                except Exception:
                    # Subscriber queue is full or closed, remove it
                    self._subscribers.discard(queue)


# Global registry of deployment log buffers
_log_buffers: dict[int, LogBuffer] = {}
_buffers_lock = asyncio.Lock()


def get_log_buffer(deployment_id: int) -> LogBuffer:
    """Get or create log buffer for a deployment.

    Args:
        deployment_id: Deployment ID

    Returns:
        Log buffer instance
    """
    if deployment_id not in _log_buffers:
        _log_buffers[deployment_id] = LogBuffer()
    return _log_buffers[deployment_id]


async def remove_log_buffer(deployment_id: int) -> None:
    """Remove log buffer for a deployment.

    Args:
        deployment_id: Deployment ID
    """
    async with _buffers_lock:
        if deployment_id in _log_buffers:
            del _log_buffers[deployment_id]


class DeploymentLogger:
    """Logger for deployment operations."""

    def __init__(self, deployment_id: int, db: Session) -> None:
        """Initialize deployment logger.

        Args:
            deployment_id: Deployment ID
            db: Database session
        """
        self.deployment_id = deployment_id
        self.db = db
        self.buffer = get_log_buffer(deployment_id)

    async def debug(self, message: str) -> None:
        """Log debug message.

        Args:
            message: Message to log
        """
        await self._log(LogLevel.DEBUG, message)

    async def info(self, message: str) -> None:
        """Log info message.

        Args:
            message: Message to log
        """
        await self._log(LogLevel.INFO, message)

    async def warning(self, message: str) -> None:
        """Log warning message.

        Args:
            message: Message to log
        """
        await self._log(LogLevel.WARNING, message)

    async def error(self, message: str) -> None:
        """Log error message.

        Args:
            message: Message to log
        """
        await self._log(LogLevel.ERROR, message)

    async def _log(self, level: LogLevel, message: str) -> None:
        """Internal log method.

        Args:
            level: Log level
            message: Message to log
        """
        # Add to in-memory buffer for SSE streaming
        await self.buffer.append(level, message)

        # Persist to database
        log_entry = DeploymentLog(
            deployment_id=self.deployment_id,
            level=level.value,
            content=message,
        )
        self.db.add(log_entry)
        self.db.commit()


async def stream_deployment_logs(
    deployment_id: int,
) -> AsyncGenerator[str, None]:
    """Stream deployment logs via Server-Sent Events.

    Args:
        deployment_id: Deployment ID

    Yields:
        SSE-formatted log messages
    """
    buffer = get_log_buffer(deployment_id)
    queue = await buffer.subscribe()

    try:
        while True:
            # Send keepalive every 30 seconds
            try:
                entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {entry.level.value} {entry.timestamp.isoformat()} {entry.content}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        await buffer.unsubscribe(queue)


def get_deployment_logs_from_db(
    db: Session,
    deployment_id: int,
    limit: int = 1000,
) -> list[DeploymentLog]:
    """Get deployment logs from database.

    Args:
        db: Database session
        deployment_id: Deployment ID
        limit: Maximum number of logs to return

    Returns:
        List of deployment logs
    """
    return (
        db.query(DeploymentLog)
        .filter(DeploymentLog.deployment_id == deployment_id)
        .order_by(DeploymentLog.timestamp)
        .limit(limit)
        .all()
    )
