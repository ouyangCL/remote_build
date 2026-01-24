# Auto Dependency Installation

## Overview

The build process now supports automatic dependency installation before running build scripts. This prevents "command not found" errors when build tools like `cross-env` are missing.

## New Project Fields

### `install_script` (optional)
- **Type**: `string | null`
- **Max Length**: 500 characters
- **Description**: Custom dependency installation command
- **Examples**:
  - `npm install` - Standard npm install
  - `npm ci` - Fast, reproducible npm install (recommended for CI/CD)
  - `yarn install` - Yarn package manager
  - `pnpm install` - pnpm package manager
  - `pip install -r requirements.txt` - Python dependencies
  - `mvn dependency:resolve` - Maven dependencies

### `auto_install` (boolean)
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Whether to automatically install dependencies before build
- **Usage**:
  - `true` - Install dependencies using default or custom command
  - `false` - Skip automatic installation (useful if dependencies are pre-installed)

## Default Behavior by Project Type

| Project Type | Default Install Command | Notes |
|-------------|------------------------|-------|
| `frontend` | `npm install` | Can be overridden with `install_script` |
| `java` | `mvn dependency:resolve` | Maven dependency resolution |
| `backend` | `None` | No default, requires explicit `install_script` |

## Usage Examples

### Example 1: Frontend Project with Defaults

```json
{
  "name": "my-frontend-app",
  "project_type": "frontend",
  "build_script": "npm run build",
  "auto_install": true
}
```

**Behavior**: Runs `npm install` automatically before `npm run build`

### Example 2: Use npm ci for Faster Installs

```json
{
  "name": "my-frontend-app",
  "project_type": "frontend",
  "build_script": "npm run build",
  "install_script": "npm ci",
  "auto_install": true
}
```

**Behavior**: Runs `npm ci` (faster, deterministic) before build

### Example 3: Yarn-based Project

```json
{
  "name": "yarn-project",
  "project_type": "frontend",
  "build_script": "yarn build",
  "install_script": "yarn install",
  "auto_install": true
}
```

**Behavior**: Runs `yarn install` before `yarn build`

### Example 4: Pre-installed Dependencies

```json
{
  "name": "cached-deps-project",
  "project_type": "frontend",
  "build_script": "npm run build",
  "auto_install": false
}
```

**Behavior**: Skips dependency installation entirely (useful with Docker image caches)

### Example 5: Python Backend

```json
{
  "name": "python-api",
  "project_type": "backend",
  "build_script": "python build.py",
  "install_script": "pip install -r requirements.txt",
  "auto_install": true
}
```

**Behavior**: Installs Python dependencies before build

## Troubleshooting

### Error: "npm: command not found"

**Cause**: Node.js/npm is not installed on the build server

**Solution**:
1. Install Node.js on the build server
2. Or use a Docker image with Node.js pre-installed
3. Or set `auto_install: false` and pre-install dependencies in your Docker image

### Error: "Dependency installation failed, continuing anyway"

**Cause**: The install command failed, but build continues (dependencies might already be installed)

**Solutions**:
1. Check if dependencies are already installed (e.g., `node_modules` exists)
2. Verify the `install_script` command is correct
3. Check build server logs for detailed error messages
4. If using custom command, test it manually in the project directory

### Build is slow with auto_install enabled

**Solutions**:
1. Use `npm ci` instead of `npm install` (faster and deterministic)
2. Set `auto_install: false` and use a Docker image with pre-installed dependencies
3. Use `node_modules` caching in your CI/CD pipeline

## Migration Guide for Existing Projects

Existing projects will automatically get `auto_install: true` and `npm install` for frontend projects.

**To disable auto-install for an existing project**:

```bash
curl -X PATCH http://your-api/projects/{project_id} \
  -H "Content-Type: application/json" \
  -d '{"auto_install": false}'
```

**To set a custom install script**:

```bash
curl -X PATCH http://your-api/projects/{project_id} \
  -H "Content-Type: application/json" \
  -d '{"install_script": "npm ci"}'
```

## Best Practices

1. **Use `npm ci` for CI/CD**: Faster and more reproducible than `npm install`
2. **Lock files**: Commit `package-lock.json`, `yarn.lock`, or `pnpm-lock.yaml` to ensure consistent installs
3. **Pre-install in Docker**: For production, use a Docker image with dependencies pre-installed and set `auto_install: false`
4. **Monitor logs**: Check deployment logs to ensure dependency installation succeeds
5. **Test locally**: Run the install command locally before deploying to ensure it works
