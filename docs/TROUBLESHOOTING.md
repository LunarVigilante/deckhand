# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the Discord Bot Control Panel.

## Table of Contents

- [Quick Diagnosis](#quick-diagnosis)
- [Database Issues](#database-issues)
- [API Issues](#api-issues)
- [Bot Issues](#bot-issues)
- [Frontend Issues](#frontend-issues)
- [Docker Issues](#docker-issues)
- [Network Issues](#network-issues)
- [Performance Issues](#performance-issues)
- [Security Issues](#security-issues)
- [Logs and Monitoring](#logs-and-monitoring)

## Quick Diagnosis

### Health Check Script
```bash
#!/bin/bash
# Run this script to quickly diagnose common issues

echo "=== Discord Bot Control Panel Health Check ==="
echo

# Check Docker services
echo "1. Docker Services Status:"
docker-compose ps
echo

# Check API health
echo "2. API Health Check:"
curl -s http://localhost:5000/health | python3 -m json.tool 2>/dev/null || echo "❌ API not responding"
echo

# Check database connectivity
echo "3. Database Connectivity:"
docker-compose exec postgres pg_isready -U discord_bot_user -d discord_bot_platform 2>/dev/null && echo "✅ Database connected" || echo "❌ Database connection failed"
echo

# Check bot status
echo "4. Bot Status:"
docker-compose logs bot 2>&1 | grep -i "ready\|connected\|error" | tail -5
echo

# Check resource usage
echo "5. Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
echo

# Check logs for errors
echo "6. Recent Errors:"
docker-compose logs --tail=20 2>&1 | grep -i error | tail -5
echo

echo "=== Diagnosis Complete ==="
```

### System Information
```bash
# Get system information
echo "System Information:"
uname -a
docker --version
docker-compose --version
echo

# Check available resources
echo "Available Resources:"
df -h /
free -h
echo

# Check network connectivity
echo "Network Status:"
curl -s --connect-timeout 5 https://discord.com/api/v10/gateway >/dev/null && echo "✅ Discord API reachable" || echo "❌ Discord API unreachable"
curl -s --connect-timeout 5 https://api.themoviedb.org >/dev/null && echo "✅ TMDB API reachable" || echo "❌ TMDB API unreachable"
```

## Database Issues

### Connection Problems
```bash
# Check PostgreSQL container status
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test database connection
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "SELECT version();"

# Check database configuration
docker-compose exec api env | grep DATABASE

# Reset database (WARNING: This will delete all data)
docker-compose down -v
docker-compose up -d postgres
```

### Migration Issues
```bash
# Check current migration status
docker-compose exec api flask db current

# Check migration history
docker-compose exec api flask db history

# Run pending migrations
docker-compose exec api flask db upgrade

# Create new migration (if schema changes)
docker-compose exec api flask db migrate -m "Description of changes"

# Reset migrations (development only)
docker-compose exec api flask db downgrade base
docker-compose exec api flask db upgrade
```

### Data Issues
```bash
# Check table sizes
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Check for corrupted data
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;"

# Backup database before troubleshooting
docker-compose exec postgres pg_dump -U discord_bot_user discord_bot_platform > backup_$(date +%Y%m%d_%H%M%S).sql
```

## API Issues

### Startup Problems
```bash
# Check API logs
docker-compose logs api

# Check API configuration
docker-compose exec api env | grep -E "(FLASK|DATABASE|REDIS)"

# Test API endpoints manually
curl -v http://localhost:5000/health
curl -v http://localhost:5000/api/v1/embeds/templates

# Check for missing dependencies
docker-compose exec api pip list | grep -E "(flask|sqlalchemy|pydantic)"

# Restart API service
docker-compose restart api
```

### Authentication Issues
```bash
# Check JWT configuration
docker-compose exec api env | grep JWT

# Test Discord OAuth flow
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"redirect_uri": "http://localhost:3000/auth/callback"}'

# Check Discord API connectivity
curl -H "Authorization: Bot YOUR_BOT_TOKEN" https://discord.com/api/v10/users/@me

# Verify OAuth2 credentials
docker-compose exec api env | grep DISCORD
```

### Rate Limiting Issues
```bash
# Check rate limit configuration
docker-compose exec api env | grep RATE_LIMIT

# Clear rate limit cache (if using Redis)
docker-compose exec redis redis-cli FLUSHALL

# Check current rate limits
curl -H "X-Forwarded-For: 127.0.0.1" http://localhost:5000/api/v1/embeds/templates
```

### CORS Issues
```bash
# Check CORS configuration
docker-compose exec api env | grep CORS

# Test CORS headers
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS http://localhost:5000/api/v1/embeds/templates
```

## Bot Issues

### Connection Problems
```bash
# Check bot logs
docker-compose logs bot

# Verify Discord token
docker-compose exec bot env | grep DISCORD_BOT_TOKEN

# Test bot token validity
curl -H "Authorization: Bot YOUR_BOT_TOKEN" https://discord.com/api/v10/users/@me

# Check bot permissions
curl -H "Authorization: Bot YOUR_BOT_TOKEN" https://discord.com/api/v10/guilds/YOUR_GUILD_ID

# Restart bot
docker-compose restart bot
```

### Command Issues
```bash
# Check command registration
docker-compose logs bot | grep -i "command\|slash"

# Test bot responsiveness
curl -H "Authorization: Bot YOUR_BOT_TOKEN" \
     -X POST https://discord.com/api/v10/channels/YOUR_CHANNEL_ID/messages \
     -H "Content-Type: application/json" \
     -d '{"content": "Test message"}'

# Check database connectivity from bot
docker-compose exec bot python3 -c "
import asyncpg
import os
async def test():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    result = await conn.fetchval('SELECT 1')
    print('Database connection:', result)
import asyncio
asyncio.run(test())
"
```

### Scheduler Issues
```bash
# Check APScheduler status
docker-compose exec bot python3 -c "
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
scheduler = AsyncIOScheduler()
print('Scheduler jobs:', len(scheduler.get_jobs()))
"

# Check scheduled tasks
docker-compose logs bot | grep -i "scheduler\|job\|task"

# Reset scheduler
docker-compose exec bot python3 -c "
import os
os.system('rm -f /app/scheduler.db')
print('Scheduler database reset')
"
```

## Frontend Issues

### Build Problems
```bash
# Check frontend logs
docker-compose logs frontend

# Rebuild frontend
docker-compose exec frontend npm run build

# Check for build errors
docker-compose exec frontend npm run build 2>&1 | head -50

# Clear node_modules and reinstall
docker-compose exec frontend rm -rf node_modules package-lock.json
docker-compose exec frontend npm install

# Check environment variables
docker-compose exec frontend env | grep VITE
```

### Runtime Issues
```bash
# Check browser console for errors
# Open Developer Tools (F12) and check Console tab

# Test API connectivity from frontend
curl http://localhost:3000
curl http://localhost:5000/api/v1/embeds/templates

# Check CORS configuration
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS http://localhost:5000/api/v1/embeds/templates

# Clear browser cache
# Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
```

### Authentication Issues
```bash
# Check OAuth2 configuration
docker-compose exec frontend env | grep VITE_DISCORD

# Test OAuth2 flow
# 1. Open http://localhost:3000
# 2. Click login
# 3. Check network tab for failed requests
# 4. Check browser console for errors

# Verify redirect URI
curl "https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fauth%2Fcallback&response_type=code&scope=identify%20guilds"
```

## Docker Issues

### Container Problems
```bash
# Check container status
docker-compose ps

# Check container logs
docker-compose logs [service_name]

# Restart specific service
docker-compose restart [service_name]

# Rebuild specific service
docker-compose up --build --force-recreate [service_name]

# Check container resource usage
docker stats

# Enter container for debugging
docker-compose exec [service_name] bash
```

### Image Issues
```bash
# Check available images
docker images

# Pull latest images
docker-compose pull

# Clean up unused images
docker image prune -f

# Build with no cache
docker-compose build --no-cache

# Check image layers
docker history [image_name]
```

### Volume Issues
```bash
# Check volume status
docker volume ls

# Inspect volume
docker volume inspect discord_bot_postgres_data

# Clean up volumes (WARNING: This will delete data)
docker-compose down -v
docker volume prune -f

# Backup volume data
docker run --rm -v discord_bot_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
```

### Network Issues
```bash
# Check Docker networks
docker network ls

# Inspect network
docker network inspect discord_bot_network

# Test inter-container connectivity
docker-compose exec api ping postgres
docker-compose exec frontend ping api

# Reset network
docker-compose down
docker network prune -f
docker-compose up -d
```

## Network Issues

### Port Conflicts
```bash
# Check port usage
netstat -tulpn | grep -E "(3000|5000|5432|6379)"

# Find process using port
lsof -i :3000

# Kill process using port
kill -9 $(lsof -t -i :3000)

# Change port mapping
# Edit docker-compose.yml and change port mappings
```

### Firewall Issues
```bash
# Check firewall status
sudo ufw status

# Allow required ports
sudo ufw allow 3000/tcp
sudo ufw allow 5000/tcp
sudo ufw allow 5432/tcp
sudo ufw allow 6379/tcp

# Check iptables rules
sudo iptables -L -n
```

### DNS Issues
```bash
# Test DNS resolution
nslookup discord.com
nslookup api.themoviedb.org

# Check /etc/resolv.conf
cat /etc/resolv.conf

# Test external connectivity
curl -I https://discord.com
curl -I https://api.themoviedb.org
```

## Performance Issues

### High CPU Usage
```bash
# Check CPU usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}"

# Check API performance
docker-compose logs api | grep -i "slow\|timeout"

# Profile Python code
docker-compose exec api python3 -m cProfile -s time /app/app.py

# Check database query performance
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC
LIMIT 5;"
```

### High Memory Usage
```bash
# Check memory usage
docker stats --format "table {{.Container}}\t{{.MemUsage}}"

# Check for memory leaks
docker-compose exec api python3 -c "
import psutil
import os
process = psutil.Process(os.getpid())
print('Memory usage:', process.memory_info().rss / 1024 / 1024, 'MB')
"

# Restart services to free memory
docker-compose restart
```

### Slow Response Times
```bash
# Test API response time
time curl -s http://localhost:5000/health > /dev/null

# Check database query performance
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "
EXPLAIN ANALYZE SELECT * FROM messagestats LIMIT 100;
"

# Check Redis performance (if used)
docker-compose exec redis redis-cli info | grep -E "(used_memory|total_connections_received|instantaneous_ops_per_sec)"

# Optimize database
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "VACUUM ANALYZE;"
```

## Security Issues

### Permission Problems
```bash
# Check file permissions
ls -la /opt/discord-bot-platform/

# Fix permissions
sudo chown -R $USER:$USER /opt/discord-bot-platform/
sudo chmod -R 755 /opt/discord-bot-platform/
sudo chmod 600 /opt/discord-bot-platform/.env

# Check Docker permissions
docker-compose exec api id
docker-compose exec postgres id
```

### SSL/TLS Issues
```bash
# Check SSL certificate
openssl s_client -connect localhost:443 -servername your-domain.com

# Test SSL configuration
curl -v https://your-domain.com/health

# Check certificate validity
openssl x509 -in /path/to/cert.pem -text -noout | grep -E "(Not Before|Not After)"

# Renew Let's Encrypt certificate
sudo certbot renew
```

### Authentication Issues
```bash
# Check JWT token validity
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:5000/api/v1/users/profile

# Verify Discord OAuth2 configuration
curl "https://discord.com/api/oauth2/token" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_AUTH_CODE"

# Check session security
docker-compose exec api env | grep SESSION
```

## Logs and Monitoring

### Log Analysis
```bash
# View all logs
docker-compose logs -f

# Search for specific errors
docker-compose logs | grep -i error

# Filter logs by time
docker-compose logs --since "1h"

# Export logs for analysis
docker-compose logs > logs_$(date +%Y%m%d_%H%M%S).log

# Monitor logs in real-time
docker-compose logs -f | grep -E "(ERROR|WARNING|CRITICAL)"
```

### Log Rotation
```bash
# Configure log rotation
cat > /etc/logrotate.d/discord-bot << EOF
/opt/discord-bot-platform/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 644 root root
    postrotate
        docker-compose restart
    endscript
}
EOF

# Test log rotation
logrotate -f /etc/logrotate.d/discord-bot
```

### Monitoring Setup
```bash
# Install monitoring tools
docker run -d --name prometheus -p 9090:9090 prom/prometheus
docker run -d --name grafana -p 3000:3000 grafana/grafana

# Check application metrics
curl http://localhost:5000/metrics

# Monitor system resources
docker run -d --name cadvisor -p 8080:8080 \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  google/cadvisor
```

## Advanced Troubleshooting

### Debug Mode
```bash
# Enable debug mode
export FLASK_ENV=development
export DEBUG=true
export LOG_LEVEL=DEBUG

# Restart with debug configuration
docker-compose up --build --force-recreate

# Debug database queries
docker-compose exec api python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from app import db
# Add debug code here
"
```

### Performance Profiling
```bash
# Profile API endpoints
docker-compose exec api python3 -c "
import cProfile
from app import create_app
app = create_app()
with app.app_context():
    cProfile.run('app.test_client().get(\"/health\")', 'profile.prof')
"

# Analyze profile
docker-compose exec api python3 -c "
import pstats
p = pstats.Stats('profile.prof')
p.sort_stats('cumulative').print_stats(10)
"
```

### Database Optimization
```bash
# Analyze query performance
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM messagestats WHERE user_id = 123456789;
"

# Check index usage
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
"

# Reindex database
docker-compose exec postgres psql -U discord_bot_user -d discord_bot_platform -c "REINDEX DATABASE discord_bot_platform;"
```

## Getting Help

### Information to Provide
When seeking help, please provide:

1. **System Information**
   ```bash
   uname -a
   docker --version
   docker-compose --version
   ```

2. **Application Logs**
   ```bash
   docker-compose logs --tail=100
   ```

3. **Configuration (without secrets)**
   ```bash
   docker-compose config
   ```

4. **Error Messages**
   - Exact error messages
   - When the error occurs
   - Steps to reproduce

5. **Environment Details**
   - Development/Production
   - Docker or native installation
   - External services used

### Support Resources
- **GitHub Issues**: Create detailed bug reports
- **Documentation**: Check [docs/](docs/) directory
- **Community**: Join Discord server for community support
- **Professional Support**: Contact maintainers for enterprise support

### Emergency Procedures
```bash
# Quick restart all services
docker-compose down && docker-compose up -d

# Emergency database backup
docker-compose exec postgres pg_dumpall -U discord_bot_user > emergency_backup_$(date +%Y%m%d_%H%M%S).sql

# Rollback to previous version
git checkout v1.0.0
docker-compose up --build -d

# Contact emergency support
echo "URGENT: Discord Bot Control Panel Down" | mail -s "System Alert" admin@your-domain.com