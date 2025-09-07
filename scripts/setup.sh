#!/bin/bash
set -e  # Exit on error

echo "=========================================="
echo "Discord Bot Media Community Platform Setup"
echo "=========================================="

# Function to check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        echo "ERROR: This script should NOT be run as root for security reasons."
        echo "Please run as a regular user with sudo privileges."
        exit 1
    fi
}

# Function to check if required tools are installed
check_dependencies() {
    local missing_deps=()

    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi

    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    fi

    if [[ ${#missing_deps[@]} -ne 0 ]]; then
        echo "Installing missing dependencies: ${missing_deps[*]}"
        sudo apt update
        sudo apt install -y "${missing_deps[@]}"
    fi
}

# Function to install Docker and Docker Compose
install_docker() {
    echo "Installing Docker..."

    # Remove old versions
    sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

    # Install Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh

    # Add user to docker group
    sudo usermod -aG docker "$USER"

    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

    echo "Docker installation complete. Please log out and back in for group changes to take effect."
}

# Function to install Node.js
install_nodejs() {
    echo "Installing Node.js 18..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt install -y nodejs
}

# Function to install Python 3.11
install_python() {
    echo "Installing Python 3.11..."
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
}

# Function to install additional tools
install_additional_tools() {
    echo "Installing additional tools..."
    sudo apt install -y postgresql-client-15 redis-tools jq tree watch htop ncdu
}

# Function to configure firewall
configure_firewall() {
    echo "Configuring firewall..."

    # Install ufw if not present
    sudo apt install -y ufw

    # Reset firewall to defaults
    sudo ufw --force reset

    # Set defaults
    sudo ufw default deny incoming
    sudo ufw default allow outgoing

    # Allow SSH
    sudo ufw allow ssh

    # Allow HTTP and HTTPS (will be restricted in production)
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp

    # For development, allow additional ports (comment out in production)
    echo "Allowing development ports (3000, 5000, 5432)..."
    sudo ufw allow 3000/tcp  # Frontend dev server
    sudo ufw allow 5000/tcp  # API dev server
    sudo ufw allow 5432/tcp  # PostgreSQL (restrict to localhost in production)

    # Enable firewall
    sudo ufw --force enable

    echo "Firewall configured. Current status:"
    sudo ufw status
}

# Function to create non-root user for application
create_app_user() {
    echo "Creating application user..."

    # Create user if it doesn't exist
    if ! id "discordbot" &>/dev/null; then
        sudo useradd --create-home --shell /bin/bash discordbot
        echo "User 'discordbot' created."
    else
        echo "User 'discordbot' already exists."
    fi

    # Add to necessary groups
    sudo usermod -aG docker discordbot 2>/dev/null || true

    # Set proper permissions on home directory
    sudo chmod 700 /home/discordbot
}

# Function to generate secure secrets
generate_secrets() {
    echo "Generating secure secrets..."

    local env_file=".env"

    # Backup existing .env if it exists
    if [[ -f "$env_file" ]]; then
        cp "$env_file" "${env_file}.backup.$(date +%Y%m%d_%H%M%S)"
        echo "Backed up existing .env file"
    fi

    # Generate Flask secret key
    local flask_secret
    flask_secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")

    # Generate JWT secret key
    local jwt_secret
    jwt_secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")

    # Generate PostgreSQL password
    local postgres_password
    postgres_password=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    # Update .env file
    if [[ -f "$env_file" ]]; then
        # Update existing values
        sed -i "s/FLASK_SECRET_KEY=.*/FLASK_SECRET_KEY=$flask_secret/" "$env_file" 2>/dev/null || echo "FLASK_SECRET_KEY=$flask_secret" >> "$env_file"
        sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$jwt_secret/" "$env_file" 2>/dev/null || echo "JWT_SECRET_KEY=$jwt_secret" >> "$env_file"
        sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$postgres_password/" "$env_file" 2>/dev/null || echo "POSTGRES_PASSWORD=$postgres_password" >> "$env_file"
    else
        # Create new .env file with basic template
        cat > "$env_file" << EOF
# Database Configuration
POSTGRES_PASSWORD=$postgres_password
DATABASE_URL=postgresql://discord_bot_user:$postgres_password@postgres:5432/discord_bot_platform

# Security Keys
FLASK_SECRET_KEY=$flask_secret
JWT_SECRET_KEY=$jwt_secret

# Add your other configuration values here
# See .env.example for all available options
EOF
    fi

    # Secure the .env file
    chmod 600 "$env_file"

    echo "Secrets generated and saved to $env_file"
    echo "IMPORTANT: Keep this file secure and never commit it to version control!"
}

# Function to verify installation
verify_installation() {
    echo "Verifying installation..."

    local errors=0

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo "ERROR: Docker not found"
        ((errors++))
    else
        echo "✓ Docker installed: $(docker --version)"
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "ERROR: Docker Compose not found"
        ((errors++))
    else
        echo "✓ Docker Compose installed: $(docker-compose --version)"
    fi

    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo "ERROR: Node.js not found"
        ((errors++))
    else
        echo "✓ Node.js installed: $(node --version)"
    fi

    # Check Python
    if ! command -v python3.11 &> /dev/null; then
        echo "ERROR: Python 3.11 not found"
        ((errors++))
    else
        echo "✓ Python 3.11 installed: $(python3.11 --version)"
    fi

    # Check Git
    if ! command -v git &> /dev/null; then
        echo "ERROR: Git not found"
        ((errors++))
    else
        echo "✓ Git installed: $(git --version)"
    fi

    # Check firewall
    if command -v ufw &> /dev/null; then
        echo "✓ UFW firewall installed"
    fi

    if [[ $errors -eq 0 ]]; then
        echo ""
        echo "🎉 Installation completed successfully!"
        echo ""
        echo "Next steps:"
        echo "1. Copy .env.example to .env and fill in your configuration"
        echo "2. Run 'docker-compose up -d' to start the services"
        echo "3. Access the application at http://localhost:3000"
        echo ""
        echo "For production deployment:"
        echo "- Update firewall rules to restrict ports"
        echo "- Configure SSL certificates with Let's Encrypt"
        echo "- Set up monitoring and logging"
    else
        echo ""
        echo "❌ Installation completed with $errors error(s)"
        echo "Please check the errors above and try again"
        exit 1
    fi
}

# Main execution
main() {
    echo "Starting setup process..."

    check_root
    check_dependencies
    install_docker
    install_nodejs
    install_python
    install_additional_tools
    configure_firewall
    create_app_user
    generate_secrets
    verify_installation

    echo ""
    echo "Setup script completed!"
    echo "Please log out and back in for Docker group changes to take effect."
}

# Run main function
main "$@"