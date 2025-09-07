## 📚 Documentation

### Getting Started
- **[README.md](README.md)** - Main project documentation
- **[API_REFERENCE.md](docs/API_REFERENCE.md)** - Complete API documentation
- **[DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)** - Deployment and scaling guide
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Troubleshooting common issues

### API Documentation
- **Interactive API Docs**: http://localhost:5000/docs (Swagger UI)
- **ReDoc Documentation**: http://localhost:5000/redoc
- **OpenAPI Specification**: http://localhost:5000/api/v1/openapi.json

### Additional Resources
- **Environment Variables**: See `.env.example` for all configuration options
- **Database Schema**: See `database/schema.sql` for complete database structure
- **Docker Configuration**: See `docker-compose.yml` for service orchestration
- **Testing**: Run `python run_tests.py --help` for testing options

## 🔧 Development

### Project Structure
```
discord-bot-platform/
├── frontend/                   # React web application
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   ├── pages/             # Page components
│   │   ├── contexts/          # React contexts
│   │   ├── services/          # API services
│   │   └── utils/             # Utility functions
│   ├── public/
│   └── package.json
├── backend/
│   ├── api/                   # Flask API server
│   │   ├── app/               # Application code
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── bot/                   # Discord bot worker
│       ├── bot/               # Bot code
│       ├── requirements.txt
│       └── Dockerfile
├── database/                  # Database schema and migrations
├── docker/                    # Docker configuration
├── docs/                      # Documentation
├── tests/                     # Test suite
└── shared/                    # Shared utilities
```

### Development Workflow
```bash
# Install frontend dependencies
cd frontend && npm install

# Start development servers
docker-compose -f docker-compose.dev.yml up

# Run tests
python run_tests.py --unit

# Format code
black backend/ tests/
npx prettier --write frontend/src/

# Lint code
flake8 backend/
npx eslint frontend/src/
```

### Code Quality
- **Black**: Python code formatting
- **Flake8**: Python linting
- **ESLint**: JavaScript/TypeScript linting
- **Prettier**: Code formatting
- **MyPy**: Type checking
- **Bandit**: Security linting

## 🚀 Deployment Options

### Docker Compose (Recommended)
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

### Cloud Platforms
- **AWS**: ECS, EKS, or Elastic Beanstalk
- **Google Cloud**: Cloud Run, GKE, or App Engine
- **Azure**: Container Instances, AKS, or App Service
- **DigitalOcean**: App Platform or Droplets with Docker

## 🧪 Testing

### Run All Tests
```bash
# Run complete test suite
python run_tests.py --all

# Run specific test types
python run_tests.py --unit
python run_tests.py --integration
python run_tests.py --security

# Generate coverage report
python run_tests.py --coverage
```

### Test Structure
```
tests/
├── conftest.py              # Test configuration and fixtures
├── test_security.py         # Security and input validation tests
├── test_api_integration.py  # API endpoint integration tests
├── test_models.py           # Database model tests
├── test_auth.py             # Authentication tests
└── test_bot.py              # Discord bot tests
```

### Test Coverage
- **Unit Tests**: Individual function/component testing
- **Integration Tests**: API endpoint and service interaction testing
- **Security Tests**: Input validation and security feature testing
- **End-to-End Tests**: Complete user workflow testing

## 🔒 Security Features

### Authentication & Authorization
- **Discord OAuth2**: Secure authentication with PKCE
- **JWT Tokens**: Stateless authentication with refresh tokens
- **Role-Based Access Control**: Server role-based permissions
- **Session Management**: Secure session handling

### Input Validation & Sanitization
- **SQL Injection Prevention**: Parameterized queries and input validation
- **XSS Protection**: HTML sanitization and content security policy
- **Input Length Limits**: Maximum length validation for all inputs
- **Type Validation**: Strict type checking for API inputs

### Security Headers
- **Content Security Policy**: XSS protection and resource restrictions
- **HSTS**: HTTP Strict Transport Security
- **X-Frame-Options**: Clickjacking protection
- **X-Content-Type-Options**: MIME type sniffing protection

### Rate Limiting
- **API Rate Limits**: Configurable per-endpoint limits
- **Authentication Limits**: Stricter limits for auth endpoints
- **Redis Backend**: Distributed rate limiting support

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow existing code style and patterns
- Write tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting PR
- Use conventional commit messages

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Common Issues
- **Database Connection**: Check PostgreSQL container is running
- **Bot Connection**: Verify Discord token and permissions
- **API Errors**: Check logs with `docker-compose logs api`
- **Frontend Issues**: Clear browser cache and rebuild

### Getting Help
- **Documentation**: Check [docs/](docs/) directory
- **Issues**: Create GitHub issue with detailed description
- **Discussions**: Use GitHub Discussions for questions
- **Logs**: Include relevant logs when reporting issues

### Troubleshooting
For detailed troubleshooting guides, see:
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)** - Deployment troubleshooting
- **Logs**: `docker-compose logs -f` for real-time monitoring

---

**Happy coding! 🎉**

For more information, visit the [documentation](docs/) or create an issue for support.# deckhand
