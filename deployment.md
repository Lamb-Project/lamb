# LAMB Production Deployment Plan

## Deploying to https://lamb.ikasten.io

**Target Environment:** Ubuntu Server (vanilla)  
**Domain:** https://lamb.ikasten.io  
**Current Status:** Working locally with Docker Compose  
**Git Status:** Clean working tree on `main` branch

You have access to the server via ssh:

ssh root@lamb.ikasten.io "YOUR DIRECT COMMAND HERE"

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Architecture Decision](#architecture-decision)
4. [Server Preparation](#server-preparation)
5. [Production Files Setup](#production-files-setup)
6. [Deployment Steps](#deployment-steps)
7. [Maintenance & Operations](#maintenance--operations)

---

## Overview

LAMB consists of 4 main services that need to be deployed:

| Service        | Local Port | Purpose                                     |
| -------------- | ---------- | ------------------------------------------- |
| **Frontend**   | 5173       | Svelte 5 web application                    |
| **Backend**    | 9099       | FastAPI server (core API)                   |
| **KB Server**  | 9090       | Knowledge Base server (document processing) |
| **Open WebUI** | 8080       | Model management interface                  |

**Deployment Strategy:** We'll use a reverse proxy (Caddy) to handle HTTPS and route traffic to these services.

---

## Prerequisites

### On Your Local Machine

- [x] Git repository clean and up-to-date
- [x] Docker Compose working locally
- [ ] SSH access to production server
- [ ] Domain control for lamb.ikasten.io

### On Production Server

- [ ] Ubuntu 22.04 LTS or newer
- [ ] Root or sudo access
- [ ] Public IP address
- [ ] Ports 80 and 443 accessible

---

## Architecture Decision

### Recommended: Single Domain with Path-Based Routing

**Domain Structure:**

```
https://lamb.ikasten.io/          → Frontend (Svelte app)
https://lamb.ikasten.io/api       → Backend API
https://lamb.ikasten.io/kb        → Knowledge Base server
https://lamb.ikasten.io/openwebui → Open WebUI interface
```

**Advantages:**

- ✅ Simpler for end users (single URL)
- ✅ No CORS issues
- ✅ Single SSL certificate
- ✅ Easier cookie/session management

---

## Server Preparation

### Step 1: Initial Server Setup

SSH into your Ubuntu server:

```bash
ssh root@<SERVER_IP>
```

### Step 2: Create Deploy User

```bash
# Create a dedicated user for deployment
adduser deploy
usermod -aG sudo deploy
usermod -aG docker deploy

# Set up SSH key authentication (recommended)
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Switch to deploy user
su - deploy
```

### Step 3: Install Required Software

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install -y docker.io docker-compose-plugin

# Install Git
sudo apt install -y git

# Install other utilities
sudo apt install -y curl wget ufw htop

# Verify installations
docker --version
git --version
```

### Step 5: Create Directory Structure

```bash
# Create application directory
sudo mkdir -p /opt/lamb
sudo chown deploy:deploy /opt/lamb

# Create data directories for persistence
sudo mkdir -p /opt/lamb/data/{backend,kb,openwebui,backups}
sudo chown -R deploy:deploy /opt/lamb/data
```

---

## Production Files Setup

### Step 1: Clone Repository

```bash
cd /opt
git clone https://github.com/Lamb-Project/lamb.git
cd lamb
```

### Step 2: Create Environment File

Create `/opt/lamb/.env`:

```bash
cat > .env << 'EOF'
# LAMB Production Environment Variables
LAMB_PROJECT_PATH=/opt/lamb
DOMAIN=lamb.ikasten.io

# Service Ports (internal)
BACKEND_PORT=9099
KB_PORT=9090
OPENWEBUI_PORT=8080

# Email for Let's Encrypt SSL certificates
LETSENCRYPT_EMAIL=admin@ikasten.io

# Environment
NODE_ENV=production
PYTHONUNBUFFERED=1
EOF
```

### Step 3: Create Caddyfile

Create `/opt/lamb/Caddyfile`:

```bash
cat > Caddyfile << 'EOF'
{
    email admin@ikasten.io
    # Uncomment for staging certificates during testing
    # acme_ca https://acme-staging-v02.api.letsencrypt.org/directory
}

lamb.ikasten.io {
    # Enable compression
    encode gzip

    # Security headers
    header {
        # Prevent clickjacking
        X-Frame-Options "SAMEORIGIN"
        # Prevent MIME sniffing
        X-Content-Type-Options "nosniff"
        # Referrer policy
        Referrer-Policy "strict-origin-when-cross-origin"
        # Remove server header
        -Server
    }

    # Backend API routes
    handle /api* {
        reverse_proxy backend:9099 {
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    # Knowledge Base routes
    handle /kb* {
        reverse_proxy kb:9090 {
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    # Open WebUI routes
    handle /openwebui* {
        reverse_proxy openwebui:8080 {
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    # Frontend - serve static files
    handle {
        root * /var/www/frontend
        try_files {path} /index.html
        file_server
    }

    # Logging
    log {
        output file /var/log/caddy/access.log
        format json
    }
}
EOF
```

### Step 4: Create Production Dockerfiles

#### Backend Dockerfile

Create `/opt/lamb/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 9099

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9099", "--forwarded-allow-ips", "*"]
```

#### KB Server Dockerfile

Create `/opt/lamb/lamb-kb-server-stable/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p static data

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 9090

CMD ["python", "start.py"]
```

#### Frontend Dockerfile

Create `/opt/lamb/frontend/svelte-app/Dockerfile`:

```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/build /usr/share/nginx/html

# Create nginx config for SPA routing
RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### Step 5: Create Production Docker Compose

Create `/opt/lamb/docker-compose.prod.yaml`:

```yaml
services:
  # Reverse Proxy with automatic HTTPS
  proxy:
    image: caddy:2-alpine
    container_name: lamb-proxy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp" # HTTP/3
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
      - caddy-logs:/var/log/caddy
      - frontend-dist:/var/www/frontend:ro
    depends_on:
      - backend
      - kb
      - openwebui
      - frontend
    networks:
      - lamb

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: lamb-backend
    restart: unless-stopped
    environment:
      - PORT=9099
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
    env_file:
      - ./backend/.env
    volumes:
      - backend-data:/app/data
      - ./lamb_v4.db:/app/lamb_v4.db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9099/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - lamb

  # Knowledge Base Server
  kb:
    build:
      context: ./lamb-kb-server-stable/backend
      dockerfile: Dockerfile
    container_name: lamb-kb-server
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
    volumes:
      - kb-data:/app/data
      - kb-static:/app/static
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9090/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - lamb

  # Open WebUI
  openwebui:
    image: python:3.11-slim
    container_name: lamb-openwebui
    restart: unless-stopped
    working_dir: /app
    environment:
      - PORT=8080
      - WEBUI_AUTH_TRUSTED_EMAIL_HEADER=X-User-Email
      - WEBUI_AUTH_TRUSTED_NAME_HEADER=X-User-Name
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
    volumes:
      - ./open-webui/backend:/app
      - openwebui-data:/app/data
      - ./open-webui/build:/app/build
    command: >
      sh -c "pip install --no-cache-dir -r requirements.txt &&
             uvicorn open_webui.main:app --host 0.0.0.0 --port 8080 --forwarded-allow-ips '*'"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - lamb

  # Frontend Builder (runs once to build, then exits)
  frontend:
    build:
      context: ./frontend/svelte-app
      dockerfile: Dockerfile
    image: lamb-frontend:latest
    container_name: lamb-frontend-builder
    volumes:
      - frontend-dist:/usr/share/nginx/html
    command: sh -c "cp -r /usr/share/nginx/html/* /usr/share/nginx/html/"
    networks:
      - lamb

volumes:
  caddy-data:
    driver: local
  caddy-config:
    driver: local
  caddy-logs:
    driver: local
  backend-data:
    driver: local
  kb-data:
    driver: local
  kb-static:
    driver: local
  openwebui-data:
    driver: local
  frontend-dist:
    driver: local

networks:
  lamb:
    name: lamb
    driver: bridge
```

### Step 6: Create .dockerignore Files

Create `/opt/lamb/.dockerignore`:

```
.git
.gitignore
*.md
.env
.env.*
node_modules
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build
.vscode
.idea
*.log
```

---

## Deployment Steps

### Step 1: Pre-Build Frontend and Open WebUI (One-time)

```bash
cd /opt/lamb

# Build Open WebUI frontend
docker run --rm \
  -v $(pwd)/open-webui:/app \
  -w /app \
  node:20-alpine \
  sh -c "npm install && npm run build"

# Verify build exists
ls -la open-webui/build/
```

### Step 2: Build Production Images

```bash
cd /opt/lamb

# Build all services
docker compose -f docker-compose.prod.yaml build

# This will take several minutes on first build
```

### Step 3: Start Services

```bash
# Start all services in detached mode
docker compose -f docker-compose.prod.yaml up -d

# Watch logs
docker compose -f docker-compose.prod.yaml logs -f
```

### Step 4: Verify Containers

```bash
# Check all containers are running
docker compose -f docker-compose.prod.yaml ps

# Expected output: All services should show "Up" status
```

---

## Post-Deployment Verification

### Step 1: Check Service Health

```bash
# Check individual service logs
docker compose -f docker-compose.prod.yaml logs backend
docker compose -f docker-compose.prod.yaml logs kb
docker compose -f docker-compose.prod.yaml logs openwebui
docker compose -f docker-compose.prod.yaml logs proxy

# Check health status
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Step 2: Test HTTPS Certificate

```bash
# From your local machine
curl -I https://lamb.ikasten.io

# Should return 200 OK with valid SSL certificate
```

### Step 3: Verify Each Service

Open in browser:

1. **Frontend:** https://lamb.ikasten.io

   - Should load the Svelte application
   - Check browser console for errors

2. **Backend API:** https://lamb.ikasten.io/api/docs

   - Should show FastAPI Swagger documentation

3. **Knowledge Base:** https://lamb.ikasten.io/kb/docs

   - Should show KB API documentation

4. **Open WebUI:** https://lamb.ikasten.io/openwebui
   - Should load the model management interface

### Step 4: Test Core Functionality

- [ ] Create a test learning assistant
- [ ] Upload a test document to KB
- [ ] Test LTI integration (if applicable)
- [ ] Verify database persistence

---

## Maintenance & Operations

### Daily Operations

#### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yaml logs -f

# Specific service
docker compose -f docker-compose.prod.yaml logs -f backend

# Last 100 lines
docker compose -f docker-compose.prod.yaml logs --tail=100
```

#### Restart Services

```bash
# Restart all
docker compose -f docker-compose.prod.yaml restart

# Restart specific service
docker compose -f docker-compose.prod.yaml restart backend
```

#### Stop Services

```bash
# Stop all (keeps data)
docker compose -f docker-compose.prod.yaml down

# Stop and remove volumes (DANGER: deletes data)
docker compose -f docker-compose.prod.yaml down -v
```

### Updates and Deployments

#### Update from Git

```bash
cd /opt/lamb

# Pull latest changes
git pull origin main

# Rebuild changed services
docker compose -f docker-compose.prod.yaml build

# Restart with new images
docker compose -f docker-compose.prod.yaml up -d

# Check logs
docker compose -f docker-compose.prod.yaml logs -f
```

#### Rollback Strategy

```bash
# Tag current version before deploying
git tag -a v1.0.0 -m "Production release 1.0.0"
git push origin v1.0.0

# To rollback
git checkout v1.0.0
docker compose -f docker-compose.prod.yaml build
docker compose -f docker-compose.prod.yaml up -d
```

### Resource Monitoring

```bash
# Container resource usage
docker stats

# Disk usage
docker system df

# Clean up unused resources
docker system prune -a
```

---
