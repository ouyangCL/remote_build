# DevOps Deployment Platform

An automated deployment platform supporting Git-based projects, build management, and one-click deployments to server groups.

## Features

- **Multi-user Support**: Role-based access control (Admin, Operator, Viewer)
- **Project Management**: Configure Git repositories, build scripts, and deployment settings
- **Server Management**: SSH connection management with server groups
- **One-Click Deployment**: Automated build and deploy pipeline
- **Real-time Logs**: SSE-based streaming logs
- **Version Rollback**: Quick rollback to previous deployments
- **Secure**: Encrypted credentials, JWT authentication

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL
- **Frontend**: Vue 3 + Element Plus + TypeScript
- **Deployment**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git
- Python 3.11+ (for local development)
- Node.js 20+ (for local development)

### Using Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd devops
```

2. Start the services:
```bash
docker-compose up -d
```

3. Initialize the admin user:
```bash
curl -X POST http://localhost/api/auth/init
```

4. Access the application:
- Frontend: http://localhost
- API: http://localhost:8000
- Default credentials: `admin` / `admin123`

### Local Development

#### Backend

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Initialize database:
```bash
alembic upgrade head
```

4. Run the server:
```bash
uvicorn app.main:app --reload
```

#### Frontend

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start dev server:
```bash
npm run dev
```

3. Access at http://localhost:5173

## Configuration

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `sqlite:///./devops.db` |
| `SECRET_KEY` | JWT signing key | - |
| `ENCRYPTION_KEY` | SSH credentials encryption key | - |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:5173` |
| `WORK_DIR` | Working directory for builds | `./work` |
| `ARTIFACTS_DIR` | Deployment artifacts directory | `./artifacts` |
| `LOGS_DIR` | Logs directory | `./logs` |

### Project Setup

1. **Create a Project**:
   - Navigate to Projects page
   - Click "New Project"
   - Configure Git URL, build script, and deployment settings

2. **Add Servers**:
   - Navigate to Servers page
   - Add servers with SSH credentials
   - Test connection before saving

3. **Create Server Groups**:
   - Navigate to Server Groups page
   - Create groups and add servers

4. **Deploy**:
   - Navigate to Deploy page
   - Select project, branch, and server groups
   - Click "Start Deployment"
   - Monitor real-time logs

## Project Structure

```
devops/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Security, SSH
│   │   ├── models/         # Database models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── db/             # Database session
│   │   ├── config.py       # Configuration
│   │   └── main.py         # Application entry
│   ├── alembic/            # Database migrations
│   └── requirements.txt
│
├── frontend/                # Vue 3 frontend
│   ├── src/
│   │   ├── api/            # API clients
│   │   ├── views/          # Page components
│   │   ├── stores/         # Pinia state
│   │   ├── router/         # Vue Router
│   │   └── types/          # TypeScript types
│   └── package.json
│
└── docker/
    ├── docker-compose.yml
    ├── Dockerfile.backend
    └── Dockerfile.frontend
```

## Deployment Flow

1. User selects project, branch, and server groups
2. Backend clones the Git repository
3. Executes custom build script
4. Packages build output as tar.gz
5. Uploads to all servers in the group via SSH
6. Executes pre-configured restart script
7. Stores artifact for rollback

## Security

- SSH passwords/keys encrypted with AES-256
- JWT token authentication
- Role-based access control
- Audit logging for all operations
- Secure HTTP headers

## License

MIT
