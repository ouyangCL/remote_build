"""Server management API routes."""
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.core.security import encrypt_data
from app.core.ssh import SSHConnectionError, create_ssh_connection, test_ssh_connection
from app.db.session import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.server import AuthType, ConnectionStatus, Server, ServerGroup
from app.models.user import User
from app.schemas.server import (
    ConnectionTestResponse,
    ServerCreate,
    ServerGroupCreate,
    ServerGroupResponse,
    ServerGroupUpdate,
    ServerResponse,
    ServerUpdate,
)
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/servers", tags=["Servers"])
groups_router = APIRouter(prefix="/api/server-groups", tags=["Server Groups"])


@router.get("", response_model=list[ServerResponse])
async def list_servers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Server]:
    """List all servers."""
    servers = db.query(Server).order_by(Server.created_at.desc()).all()
    return cast(list[Server], servers)


@router.post("", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    server_data: ServerCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Server:
    """Create a new server."""
    existing = db.query(Server).filter(Server.name == server_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server name already exists",
        )

    encrypted_auth = encrypt_data(server_data.auth_value)

    server = Server(
        **server_data.model_dump(exclude={"auth_value"}),
        auth_value=encrypted_auth,
    )
    db.add(server)
    db.commit()
    db.refresh(server)

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.SERVER_CREATE,
        resource_type="server",
        resource_id=server.id,
        details={"server_name": server.name},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return cast(Server, server)


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Server:
    """Get a server by ID."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    return cast(Server, server)


@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: int,
    server_data: ServerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> Server:
    """Update a server."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    for field, value in server_data.model_dump(exclude_unset=True).items():
        if field == "auth_value":
            # Only update auth_value if a new value is provided (not empty string)
            if value is not None and value != "":
                value = encrypt_data(value)
                setattr(server, field, value)
            # If value is None or empty string, keep the existing auth_value
        else:
            setattr(server, field, value)

    db.commit()
    db.refresh(server)

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.SERVER_UPDATE,
        resource_type="server",
        resource_id=server.id,
        details={"server_name": server.name},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return cast(Server, server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> None:
    """Delete a server."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    server_name = server.name
    db.delete(server)
    db.commit()

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.SERVER_DELETE,
        resource_type="server",
        resource_id=server_id,
        details={"server_name": server_name},
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post("/{server_id}/test-connection", response_model=ConnectionTestResponse)
async def test_server_connection(
    server_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> ConnectionTestResponse:
    """Test SSH connection to a server and update connection status."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    try:
        success = test_ssh_connection(server)
        if success:
            # Update connection status to online
            server.connection_status = ConnectionStatus.ONLINE
            db.commit()
            return ConnectionTestResponse(success=True, message="连接成功")
        else:
            # Update connection status to offline
            server.connection_status = ConnectionStatus.OFFLINE
            db.commit()
            return ConnectionTestResponse(success=False, message="连接失败")
    except SSHConnectionError as e:
        # Update connection status to offline
        server.connection_status = ConnectionStatus.OFFLINE
        db.commit()
        return ConnectionTestResponse(success=False, message=str(e))


@groups_router.get("", response_model=list[ServerGroupResponse])
async def list_server_groups(
    environment: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ServerGroup]:
    """List all server groups, optionally filtered by environment."""
    query = db.query(ServerGroup)

    if environment:
        query = query.filter(ServerGroup.environment == environment)

    groups = query.order_by(ServerGroup.created_at.desc()).all()
    return cast(list[ServerGroup], groups)


@groups_router.post("", response_model=ServerGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_server_group(
    group_data: ServerGroupCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> ServerGroup:
    """Create a new server group."""
    existing = db.query(ServerGroup).filter(ServerGroup.name == group_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server group name already exists",
        )

    group = ServerGroup(
        name=group_data.name,
        description=group_data.description,
        environment=group_data.environment,
    )
    db.add(group)
    db.commit()

    if group_data.server_ids:
        for server_id in group_data.server_ids:
            server = db.query(Server).filter(Server.id == server_id).first()
            if server:
                group.servers.append(server)

    db.commit()
    db.refresh(group)

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.SERVER_GROUP_CREATE,
        resource_type="server_group",
        resource_id=group.id,
        details={"group_name": group.name, "environment": group.environment},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return cast(ServerGroup, group)


@groups_router.get("/{group_id}", response_model=ServerGroupResponse)
async def get_server_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ServerGroup:
    """Get a server group by ID."""
    group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server group not found",
        )

    return cast(ServerGroup, group)


@groups_router.put("/{group_id}", response_model=ServerGroupResponse)
async def update_server_group(
    group_id: int,
    group_data: ServerGroupUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> ServerGroup:
    """Update a server group."""
    group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server group not found",
        )

    if group_data.name is not None:
        group.name = group_data.name
    if group_data.description is not None:
        group.description = group_data.description
    if group_data.environment is not None:
        group.environment = group_data.environment

    if group_data.server_ids is not None:
        group.servers.clear()
        for server_id in group_data.server_ids:
            server = db.query(Server).filter(Server.id == server_id).first()
            if server:
                group.servers.append(server)

    db.commit()
    db.refresh(group)

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.SERVER_GROUP_UPDATE,
        resource_type="server_group",
        resource_id=group.id,
        details={"group_name": group.name, "environment": group.environment},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return cast(ServerGroup, group)


@groups_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server_group(
    group_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> None:
    """Delete a server group."""
    group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server group not found",
        )

    group_name = group.name
    db.delete(group)
    db.commit()

    # Log audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    create_audit_log(
        db=db,
        user_id=current_admin.id,
        action=AuditAction.SERVER_GROUP_DELETE,
        resource_type="server_group",
        resource_id=group_id,
        details={"group_name": group_name},
        ip_address=ip_address,
        user_agent=user_agent,
    )
