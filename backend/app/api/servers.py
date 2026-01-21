"""Server management API routes."""
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import encrypt_data
from app.core.ssh import SSHConnectionError, create_ssh_connection, test_ssh_connection
from app.db.session import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.server import AuthType, Server, ServerGroup
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
        if field == "auth_value" and value is not None:
            value = encrypt_data(value)
        setattr(server, field, value)

    db.commit()
    db.refresh(server)

    return cast(Server, server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: int,
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

    db.delete(server)
    db.commit()


@router.post("/{server_id}/test-connection", response_model=ConnectionTestResponse)
async def test_server_connection(
    server_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> ConnectionTestResponse:
    """Test SSH connection to a server."""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    try:
        success = test_ssh_connection(server)
        if success:
            return ConnectionTestResponse(success=True, message="Connection successful")
        else:
            return ConnectionTestResponse(success=False, message="Connection failed")
    except SSHConnectionError as e:
        return ConnectionTestResponse(success=False, message=str(e))


@groups_router.get("", response_model=list[ServerGroupResponse])
async def list_server_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ServerGroup]:
    """List all server groups."""
    groups = db.query(ServerGroup).order_by(ServerGroup.created_at.desc()).all()
    return cast(list[ServerGroup], groups)


@groups_router.post("", response_model=ServerGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_server_group(
    group_data: ServerGroupCreate,
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

    if group_data.server_ids is not None:
        group.servers.clear()
        for server_id in group_data.server_ids:
            server = db.query(Server).filter(Server.id == server_id).first()
            if server:
                group.servers.append(server)

    db.commit()
    db.refresh(group)

    return cast(ServerGroup, group)


@groups_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server_group(
    group_id: int,
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

    db.delete(group)
    db.commit()
