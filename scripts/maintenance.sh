#!/bin/bash
set -e  # Exit on error

echo "=========================================="
echo "Discord Bot Platform Maintenance Script"
echo "=========================================="

# Configuration
BACKUP_DIR="./backups"
LOG_DIR="./logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to create backup directory
create_backup_dir() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        mkdir -p "$BACKUP_DIR"
        print_status "Created backup directory: $BACKUP_DIR"
    fi
}

# Function to backup database
backup_database() {
    print_status "Starting database backup..."

    local backup_file="$BACKUP_DIR/postgres_backup_$TIMESTAMP.sql.gz"

    # Create backup
    docker-compose exec -T postgres pg_dump -U discord_bot_user -d discord_bot_platform | gzip > "$backup_file"

    # Verify backup
    if [[ -f "$backup_file" ]] && [[ -s "$backup_file" ]]; then
        local size
        size=$(du -h "$backup_file" | cut -f1)
        print_status "Database backup created: $backup_file ($size)"

        # Keep only last 7 backups
        cd "$BACKUP_DIR" || exit
        ls -t postgres_backup_*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm -f
        cd - >/dev/null || exit

        print_status "Old backups cleaned up (keeping last 7)"
    else
        print_error "Database backup failed!"
        exit 1
    fi
}

# Function to backup environment and configuration
backup_config() {
    print_status "Backing up configuration files..."

    local config_backup="$BACKUP_DIR/config_backup_$TIMESTAMP.tar.gz"

    # Backup important files
    tar -czf "$config_backup" \
        .env \
        docker-compose.yml \
        docker-compose.override.yml 2>/dev/null || true

    if [[ -f "$config_backup" ]]; then
        print_status "Configuration backup created: $config_backup"
    else
        print_warning "No configuration files to backup"
    fi
}

# Function to rotate JWT secret
rotate_jwt_secret() {
    print_status "Rotating JWT secret key..."

    # Generate new secret
    local new_secret
    new_secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")

    # Backup current .env
    cp .env ".env.backup.$TIMESTAMP"

    # Update JWT secret
    sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$new_secret/" .env

    print_status "JWT secret rotated. Old secret backed up to .env.backup.$TIMESTAMP"

    # Restart API to use new key
    print_status "Restarting API service..."
    docker-compose restart api

    print_warning "NOTE: Existing JWT tokens will be invalidated. Users will need to re-authenticate."
}

# Function to check service health
check_health() {
    print_status "Checking service health..."

    local services=("postgres" "redis" "api" "bot" "frontend")
    local failed_services=()

    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "Up"; then
            print_status "✓ $service is running"
        else
            print_error "✗ $service is not running"
            failed_services+=("$service")
        fi
    done

    if [[ ${#failed_services[@]} -gt 0 ]]; then
        print_warning "Failed services: ${failed_services[*]}"
        return 1
    else
        print_status "All services are healthy"
        return 0
    fi
}

# Function to clean up Docker resources
cleanup_docker() {
    print_status "Cleaning up Docker resources..."

    # Remove unused containers
    docker container prune -f

    # Remove unused images
    docker image prune -f

    # Remove unused volumes
    docker volume prune -f

    # Remove unused networks
    docker network prune -f

    print_status "Docker cleanup completed"
}

# Function to check disk usage
check_disk_usage() {
    print_status "Checking disk usage..."

    local usage
    usage=$(df -h . | tail -1 | awk '{print $5}' | sed 's/%//')

    if [[ $usage -gt 90 ]]; then
        print_error "Disk usage is high: ${usage}%"
        print_warning "Consider cleaning up old backups or logs"
    elif [[ $usage -gt 75 ]]; then
        print_warning "Disk usage is moderate: ${usage}%"
    else
        print_status "Disk usage is normal: ${usage}%"
    fi
}

# Function to check logs for errors
check_logs() {
    print_status "Checking logs for errors..."

    local error_count
    error_count=$(docker-compose logs --tail=1000 2>&1 | grep -i error | wc -l)

    if [[ $error_count -gt 0 ]]; then
        print_warning "Found $error_count error(s) in recent logs"
        print_status "Run 'docker-compose logs' to see detailed error messages"
    else
        print_status "No errors found in recent logs"
    fi
}

# Function to update dependencies
update_dependencies() {
    print_status "Updating dependencies..."

    # Update Python dependencies
    print_status "Updating Python requirements..."
    docker-compose exec api pip list --outdated
    docker-compose exec bot pip list --outdated

    # Update Node.js dependencies
    print_status "Updating Node.js dependencies..."
    docker-compose exec frontend npm outdated

    print_warning "Manual review required for dependency updates"
    print_status "Consider updating requirements.txt and package.json files"
}

# Function to run security scan
security_scan() {
    print_status "Running security scan..."

    # Check for vulnerable Python packages
    if command -v pip-audit &> /dev/null; then
        print_status "Scanning Python packages for vulnerabilities..."
        docker-compose exec api pip-audit || print_warning "pip-audit failed, consider installing it"
    else
        print_warning "pip-audit not installed. Install with: pip install pip-audit"
    fi

    # Check for vulnerable Node.js packages
    print_status "Scanning Node.js packages for vulnerabilities..."
    docker-compose exec frontend npm audit || print_warning "npm audit completed with warnings"

    # Check file permissions
    print_status "Checking file permissions..."
    if [[ $(stat -c %a .env 2>/dev/null) != "600" ]]; then
        print_warning ".env file permissions are not secure (should be 600)"
    fi
}

# Function to show usage
usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  backup          Create database and configuration backups"
    echo "  health          Check health of all services"
    echo "  cleanup         Clean up Docker resources"
    echo "  disk            Check disk usage"
    echo "  logs            Check logs for errors"
    echo "  update          Check for dependency updates"
    echo "  security        Run security scan"
    echo "  rotate-jwt      Rotate JWT secret key"
    echo "  all             Run all maintenance tasks"
    echo "  help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 backup"
    echo "  $0 all"
}

# Main execution
main() {
    local command=${1:-"help"}

    case $command in
        backup)
            create_backup_dir
            backup_database
            backup_config
            ;;
        health)
            check_health
            ;;
        cleanup)
            cleanup_docker
            ;;
        disk)
            check_disk_usage
            ;;
        logs)
            check_logs
            ;;
        update)
            update_dependencies
            ;;
        security)
            security_scan
            ;;
        rotate-jwt)
            rotate_jwt_secret
            ;;
        all)
            print_status "Running all maintenance tasks..."
            create_backup_dir
            backup_database
            backup_config
            check_health
            cleanup_docker
            check_disk_usage
            check_logs
            update_dependencies
            security_scan
            ;;
        help|*)
            usage
            ;;
    esac
}

# Run main function
main "$@"