# Deployment Guide

This guide covers deploying the Discord Bot Control Panel to various environments including development, staging, and production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [Production Deployment](#production-deployment)
- [SSL/TLS Configuration](#ssltls-configuration)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Troubleshooting](#troubleshooting)
- [Backup and Recovery](#backup-and-recovery)

## Prerequisites

### System Requirements
- **Docker**: Version 24.0 or later
- **Docker Compose**: Version 2.0 or later
- **Git**: For cloning the repository
- **SSL Certificate**: For HTTPS (Let's Encrypt recommended)

### External Services
- **Discord Application**: Bot token and OAuth2 credentials
- **PostgreSQL Database**: Version 15+ (or use Docker)
- **Redis**: Version 7+ (optional, for caching)
- **External APIs**: TMDB, Anilist, TheTVDB, OpenRouter

### Network Requirements
- **Ports**: 80/443 (HTTP/HTTPS), 5432 (PostgreSQL), 6379 (Redis)
- **Domain**: Registered domain name for production
- **DNS**: A/AAAA records pointing to your server

## Local Development

### Quick Start
```bash
# Clone repository
git clone <repository-url>
cd discord-bot-platform

# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env

# Start development environment
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Access application
# Frontend: http://localhost:3000
# API: http://localhost:5000
# API Docs: http://localhost:5000/docs
```

### Development Configuration
```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
      target: development
    volumes:
      - ../frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://localhost:5000
    ports:
      - "3000:3000"

  api:
    environment:
      - FLASK_ENV=development
      - DEBUG=true
    volumes:
      - ./backend/api:/app
```

### Development Tools
```bash
# View logs
docker-compose logs -f

# Access containers
docker-compose exec api bash
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform

# Run tests
docker-compose exec api python -m pytest tests/

# Rebuild specific service
docker-compose up --build --force-recreate frontend
```

## Docker Deployment

### Basic Docker Compose
```bash
# Production deployment
docker-compose up -d

# With custom configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Scale services
docker-compose up -d --scale api=3

# Update deployment
docker-compose pull && docker-compose up -d
```

### Docker Compose Override Files

#### docker-compose.prod.yml
```yaml
version: '3.8'

services:
  postgres:
    environment:
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
    secrets:
      - postgres_password
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  redis:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

  api:
    environment:
      - FLASK_ENV=production
      - LOG_LEVEL=INFO
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s

  bot:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'

  frontend:
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
        reservations:
          memory: 128M
          cpus: '0.25'

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
```

### Docker Swarm Deployment
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml discord_bot

# View services
docker stack services discord_bot

# Scale services
docker service scale discord_bot_api=3

# Update stack
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml discord_bot
```

## Production Deployment

### Server Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create application directory
sudo mkdir -p /opt/discord-bot-platform
sudo chown $USER:$USER /opt/discord-bot-platform
cd /opt/discord-bot-platform
```

### Application Deployment
```bash
# Clone repository
git clone <repository-url> .
git checkout main

# Create environment file
cp .env.example .env
nano .env

# Create secrets directory
mkdir -p secrets
echo "your_secure_postgres_password" > secrets/postgres_password.txt
chmod 600 secrets/postgres_password.txt

# Create logs directory
mkdir -p logs
chmod 755 logs

# Start application
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify deployment
docker-compose ps
curl -f http://localhost/health
```

### Nginx Reverse Proxy (Optional)
```nginx
# /etc/nginx/sites-available/discord-bot-platform
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://localhost:5000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## SSL/TLS Configuration

### Let's Encrypt (Recommended)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Automatic renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Manual SSL Configuration
```yaml
# docker-compose.ssl.yml
version: '3.8'

services:
  frontend:
    environment:
      - NGINX_SSL_CERT=/etc/ssl/certs/your_domain.crt
      - NGINX_SSL_KEY=/etc/ssl/private/your_domain.key
    volumes:
      - ./ssl/your_domain.crt:/etc/ssl/certs/your_domain.crt:ro
      - ./ssl/your_domain.key:/etc/ssl/private/your_domain.key:ro
    ports:
      - "443:443"
```

### SSL Configuration for Nginx
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/ssl/certs/your_domain.crt;
    ssl_certificate_key /etc/ssl/private/your_domain.key;

    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://localhost:5000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

## Monitoring and Maintenance

### Health Checks
```bash
# Check all services
docker-compose ps

# Check API health
curl -f http://localhost:5000/health

# Check detailed health
curl -f http://localhost:5000/health/detailed

# Check database connectivity
docker-compose exec postgres pg_isready -U discord_bot_user -d discord_bot_platform
```

### Log Management
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f bot

# Export logs
docker-compose logs > logs/$(date +%Y%m%d_%H%M%S)_all_services.log

# Log rotation
docker-compose exec api logrotate /etc/logrotate.d/api
```

### Performance Monitoring
```bash
# Check resource usage
docker stats

# Check disk usage
docker system df

# Clean up unused resources
docker system prune -f
docker volume prune -f
```

### Automated Maintenance
```bash
# Create maintenance script
cat > maintenance.sh << 'EOF'
#!/bin/bash

# Update application
cd /opt/discord-bot-platform
git pull origin main

# Update Docker images
docker-compose pull

# Restart services
docker-compose up -d

# Clean up
docker system prune -f

# Health check
sleep 30
curl -f http://localhost/health || echo "Health check failed"
EOF

chmod +x maintenance.sh

# Add to cron for weekly maintenance
# 0 2 * * 1 /opt/discord-bot-platform/maintenance.sh
```

## Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check PostgreSQL container
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test database connection
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "SELECT version();"

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

#### Bot Connection Issues
```bash
# Check bot logs
docker-compose logs bot

# Verify Discord token
docker-compose exec bot python -c "import os; print('Token exists:', bool(os.getenv('DISCORD_BOT_TOKEN')))"

# Check bot permissions
# Ensure bot has necessary permissions in Discord Developer Portal
```

#### API Issues
```bash
# Check API logs
docker-compose logs api

# Test API endpoints
curl -f http://localhost:5000/health
curl -f http://localhost:5000/api/v1/embeds/templates

# Check environment variables
docker-compose exec api env | grep -E "(DATABASE|REDIS|DISCORD)"
```

#### Frontend Issues
```bash
# Check frontend logs
docker-compose logs frontend

# Clear browser cache
# Check network tab for failed requests

# Rebuild frontend
docker-compose exec frontend npm run build
```

### Debug Mode
```bash
# Enable debug logging
export FLASK_ENV=development
export DEBUG=true
export LOG_LEVEL=DEBUG

# Restart services
docker-compose up --build --force-recreate
```

### Performance Issues
```bash
# Check resource usage
docker stats

# Check database performance
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "SELECT * FROM pg_stat_activity;"

# Check Redis (if used)
docker-compose exec redis redis-cli info

# Optimize Docker resources
docker system prune -f
```

## Backup and Recovery

### Database Backup
```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/opt/discord-bot-platform/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/discord_bot_$DATE.sql"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create database backup
docker-compose exec -T postgres pg_dump -U discord_bot_user discord_bot_platform > $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE.gz"
EOF

chmod +x backup.sh

# Run backup
./backup.sh

# Add to cron for daily backups
# 0 2 * * * /opt/discord-bot-platform/backup.sh
```

### Database Restore
```bash
# Stop services
docker-compose down

# Restore from backup
gunzip backup_file.sql.gz
docker-compose exec -T postgres psql -U discord_bot_user -d discord_bot_platform < backup_file.sql

# Start services
docker-compose up -d
```

### Configuration Backup
```bash
# Backup configuration
tar -czf config_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    .env \
    docker-compose.yml \
    docker-compose.prod.yml \
    secrets/ \
    ssl/
```

### Disaster Recovery
```bash
# Complete recovery procedure
# 1. Stop all services
docker-compose down

# 2. Restore database
./restore_database.sh

# 3. Restore configuration
tar -xzf config_backup.tar.gz

# 4. Update application code
git pull origin main

# 5. Rebuild and restart
docker-compose up --build -d

# 6. Verify health
curl -f http://localhost/health
```

## Security Best Practices

### Container Security
```yaml
# Security-focused docker-compose
services:
  api:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    user: "1000:1000"

  postgres:
    security_opt:
      - no-new-privileges:true
    user: "999:999"
```

### Network Security
```bash
# Configure firewall
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw default deny incoming
sudo ufw default allow outgoing
```

### Secrets Management
```bash
# Use Docker secrets in production
echo "your_secret_password" | docker secret create postgres_password -

# Or use external secret management (Vault, AWS Secrets Manager, etc.)
```

## Scaling

### Horizontal Scaling
```bash
# Scale API service
docker-compose up -d --scale api=3

# Load balancer configuration (nginx)
upstream api_backend {
    server api:5000;
    server api2:5000;
    server api3:5000;
}

server {
    listen 80;
    location /api/ {
        proxy_pass http://api_backend;
    }
}
```

### Database Scaling
```yaml
# Database read replicas
services:
  postgres_master:
    # Primary database

  postgres_replica:
    image: postgres:15
    environment:
      - POSTGRES_MASTER_HOST=postgres_master
      - POSTGRES_MASTER_PORT=5432
    command: ["postgres", "-c", "hot_standby=on"]
```

### Monitoring Scaling
```bash
# Prometheus + Grafana setup
docker run -d \
  -p 9090:9090 \
  -v /opt/prometheus:/etc/prometheus \
  prom/prometheus

docker run -d \
  -p 3000:3000 \
  grafana/grafana
```

## Support

For deployment issues:
1. Check logs: `docker-compose logs`
2. Verify configuration: `docker-compose config`
3. Test connectivity: `docker-compose exec api curl -f http://localhost:5000/health`
4. Check resource usage: `docker stats`
5. Review documentation: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

For production support, consider:
- Monitoring services (DataDog, New Relic)
- Log aggregation (ELK stack, Loki)
- Backup solutions (automated cloud backups)
- Load balancing (nginx, HAProxy)
- Container orchestration (Kubernetes, Docker Swarm)