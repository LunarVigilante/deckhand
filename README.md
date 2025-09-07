# Discord Bot Media Community Platform

A comprehensive, production-ready Discord bot platform with React frontend, Flask API backend, and discord.py bot worker. Features media search, LLM chat, embed management, giveaways, statistics, and more.

## 🚀 Quick Start

### Prerequisites
- Ubuntu 20.04+ or similar Linux distribution
- At least 4GB RAM, 2 CPU cores, 20GB storage
- Root or sudo access for initial setup

### Automated Setup (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd discord-bot-platform

# Run the automated setup script (handles all security configurations)
bash scripts/setup.sh

# Configure your environment variables
cp .env.example .env
nano .env  # Fill in your API keys and configuration

# Start the platform
docker-compose up -d

# Run comprehensive tests
bash scripts/test.sh --all

# Access the application
# Frontend: http://localhost:3000
# API Docs: http://localhost:5000/docs
```

### Manual Setup
See [SETUP.md](SETUP.md) for detailed manual installation instructions.

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend│    │   Flask API     │    │ Discord.py Bot  │
│   (Vite)        │◄──►│   (REST API)    │◄──►│   (Worker)      │
│                 │    │                 │    │                 │
│ - Dashboard     │    │ - Auth (OAuth2) │    │ - Slash Commands│
│ - Embed Builder │    │ - CRUD Endpoints│    │ - Event Handlers│
│ - Statistics    │    │ - Rate Limiting │    │ - Scheduled Tasks│
│ - Media Tools   │    │ - Caching       │    │ - API Integrations│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │ PostgreSQL DB  │
                    │   + Redis      │
                    │   (Caching)    │
                    └─────────────────┘
```

## 🔒 Security Features

### High-Security Configuration
- **Non-root containers**: All services run as non-root users (1000:1000)
- **Resource limits**: Memory and CPU limits prevent resource exhaustion
- **Secret management**: Auto-generated secure secrets with rotation
- **Firewall hardening**: UFW with minimal open ports
- **Input validation**: Comprehensive sanitization and validation
- **Rate limiting**: Per-endpoint and global rate limits
- **Audit logging**: Complete request/response logging
- **HTTPS ready**: SSL/TLS configuration with Let's Encrypt

### Security Best Practices
- OWASP Top 10 compliance
- Docker CIS benchmarks adherence
- PEP 8 Python standards
- SOC 2 ready logging
- Automated security scanning
- Dependency vulnerability monitoring

## 📊 Features

### 🤖 Discord Bot Features
- **Media Search**: TMDB, Anilist, TheTVDB integration
- **LLM Chat**: OpenRouter-powered AI conversations
- **Embed Management**: WYSIWYG editor with live preview
- **Giveaway System**: Automated winner selection
- **Statistics Engine**: Real-time analytics and reporting
- **Watch Parties**: Discord Events API integration
- **Auto-moderation**: Content filtering and spam prevention

### 🌐 Web Dashboard Features
- **User Authentication**: Discord OAuth2 with PKCE
- **Role-Based Access Control**: Granular permissions
- **Real-time Statistics**: Charts and analytics
- **Embed Builder**: Drag-and-drop editor
- **Media Management**: Search and organize content
- **Giveaway Manager**: Create and monitor giveaways
- **Audit Logs**: Complete activity tracking

### 🔧 API Features
- **RESTful Design**: Clean, documented endpoints
- **Rate Limiting**: Configurable per-endpoint limits
- **Caching**: Redis-backed response caching
- **Health Checks**: Comprehensive monitoring
- **Swagger Documentation**: Interactive API docs
- **Webhook Support**: Real-time notifications

## 🛠️ Technology Stack

### Backend
- **Python 3.11**: Core language
- **Flask**: Web framework with RESTX
- **SQLAlchemy**: ORM with Alembic migrations
- **PostgreSQL**: Primary database
- **Redis**: Caching and sessions
- **discord.py**: Bot framework
- **Pydantic**: Data validation
- **Structlog**: Structured logging

### Frontend
- **React 18**: UI framework
- **Vite**: Build tool and dev server
- **TypeScript**: Type safety
- **Material-UI**: Component library
- **React Router**: Navigation
- **Zustand**: State management
- **Recharts**: Data visualization

### DevOps
- **Docker**: Containerization
- **Docker Compose**: Orchestration
- **nginx**: Reverse proxy and load balancing
- **Let's Encrypt**: SSL certificates
- **Prometheus**: Monitoring
- **Grafana**: Dashboards

## 🚀 Deployment

### Production Deployment
```bash
# Use production docker-compose override
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Set up SSL certificates
certbot --nginx -d your-domain.com

# Configure monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

### Scaling
```bash
# Scale API instances
docker-compose up -d --scale api=3

# Scale bot workers
docker-compose up -d --scale bot=2
```

## 📈 Monitoring & Maintenance

### Health Checks
```bash
# Check all services
bash scripts/test.sh --services

# Detailed health check
curl http://localhost:5000/health/detailed
```

### Maintenance Tasks
```bash
# Run all maintenance tasks
bash scripts/maintenance.sh --all

# Backup database
bash scripts/maintenance.sh --backup

# Rotate secrets
bash scripts/maintenance.sh --rotate-jwt
```

### Monitoring Stack
- **Health Checks**: Automated service monitoring
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **Alert Manager**: Notification system
- **ELK Stack**: Log aggregation and analysis

## 🔧 Configuration

### Environment Variables
See `.env.example` for all configuration options. Key variables:

```bash
# Database
POSTGRES_PASSWORD=your_secure_password
DATABASE_URL=postgresql://user:pass@host:5432/db

# Discord
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret

# APIs
OPENROUTER_API_KEY=your_openrouter_key
TMDB_API_KEY=your_tmdb_key

# Security
FLASK_SECRET_KEY=your_flask_secret
JWT_SECRET_KEY=your_jwt_secret
```

### Docker Configuration
- **Resource Limits**: Configured in `docker-compose.yml`
- **Health Checks**: Automatic service monitoring
- **Logging**: JSON format with rotation
- **Networks**: Isolated service communication

## 🧪 Testing

### Automated Testing
```bash
# Run all tests
bash scripts/test.sh --all

# Test specific components
bash scripts/test.sh --backend    # API and bot tests
bash scripts/test.sh --frontend   # React tests
bash scripts/test.sh --performance # Load testing
```

### Manual Testing
```bash
# Test API endpoints
curl http://localhost:5000/health

# Test bot connectivity
docker-compose logs bot

# Test database connection
docker-compose exec postgres pg_isready
```

## 📚 API Documentation

### Authentication
```bash
# Login with Discord OAuth2
GET /api/v1/auth/login

# Refresh token
POST /api/v1/auth/refresh

# Logout
POST /api/v1/auth/logout
```

### Core Endpoints
```bash
# Health check
GET /health

# User management
GET /api/v1/users
POST /api/v1/users

# Embed management
GET /api/v1/embeds
POST /api/v1/embeds

# Statistics
GET /api/v1/stats/dashboard
GET /api/v1/stats/users

# Media search
GET /api/v1/media/search?q=movie_title

# Giveaways
GET /api/v1/giveaways
POST /api/v1/giveaways
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `bash scripts/test.sh --all`
4. Submit a pull request

### Development Setup
```bash
# Install dependencies
npm install
pip install -r backend/api/requirements.txt
pip install -r backend/bot/requirements.txt

# Start development servers
docker-compose -f docker-compose.dev.yml up -d
npm run dev
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Troubleshooting
- Check logs: `docker-compose logs`
- Run diagnostics: `bash scripts/test.sh --services`
- View health status: `curl http://localhost:5000/health`

### Common Issues
- **Port conflicts**: Check `netstat -tlnp`
- **Permission errors**: Ensure proper file permissions
- **Database connection**: Verify PostgreSQL is running
- **Bot not responding**: Check Discord token and permissions

### Documentation
- [Setup Guide](SETUP.md)
- [API Documentation](API.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Troubleshooting](TROUBLESHOOTING.md)

## 🎯 Roadmap

### Upcoming Features
- [ ] Mobile app (React Native)
- [ ] Voice channel integration
- [ ] Advanced analytics dashboard
- [ ] Multi-server support
- [ ] Plugin system
- [ ] Backup and restore
- [ ] Multi-language support

### Performance Improvements
- [ ] Database query optimization
- [ ] CDN integration
- [ ] Horizontal scaling
- [ ] Caching layer expansion
- [ ] Background job processing

---

**Built with ❤️ for the Discord community**

*For questions or support, please open an issue on GitHub.*
