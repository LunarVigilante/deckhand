#!/bin/bash
set -e  # Exit on error

echo "=========================================="
echo "Discord Bot Platform Test Suite"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://localhost:5000"
FRONTEND_URL="http://localhost:3000"
TEST_RESULTS="./test_results_$(date +%Y%m%d_%H%M%S).log"

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to print colored output
print_header() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED_TESTS++))
}

print_failure() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED_TESTS++))
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Function to log test results
log_result() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$TEST_RESULTS"
}

# Function to check if service is running
check_service() {
    local service=$1
    local url=$2
    local timeout=${3:-10}

    ((TOTAL_TESTS++))
    print_header "Checking $service at $url"

    if curl -f -s --max-time "$timeout" "$url" >/dev/null 2>&1; then
        print_success "$service is responding"
        log_result "PASS: $service is responding"
        return 0
    else
        print_failure "$service is not responding"
        log_result "FAIL: $service is not responding"
        return 1
    fi
}

# Function to test API health endpoint
test_api_health() {
    ((TOTAL_TESTS++))
    print_header "Testing API health endpoint"

    local response
    response=$(curl -s "$API_URL/health" 2>/dev/null)

    if [[ $? -eq 0 ]] && echo "$response" | jq -e '.status == "healthy"' >/dev/null 2>&1; then
        print_success "API health check passed"
        log_result "PASS: API health check"
        return 0
    else
        print_failure "API health check failed"
        log_result "FAIL: API health check - Response: $response"
        return 1
    fi
}

# Function to test database connection
test_database_connection() {
    ((TOTAL_TESTS++))
    print_header "Testing database connection"

    local result
    result=$(docker-compose exec -T postgres pg_isready -U discord_bot_user -d discord_bot_platform 2>/dev/null)

    if [[ $? -eq 0 ]] && echo "$result" | grep -q "accepting connections"; then
        print_success "Database connection successful"
        log_result "PASS: Database connection"
        return 0
    else
        print_failure "Database connection failed"
        log_result "FAIL: Database connection - Result: $result"
        return 1
    fi
}

# Function to test Redis connection
test_redis_connection() {
    ((TOTAL_TESTS++))
    print_header "Testing Redis connection"

    local result
    result=$(docker-compose exec -T redis redis-cli ping 2>/dev/null)

    if [[ $? -eq 0 ]] && [[ "$result" == "PONG" ]]; then
        print_success "Redis connection successful"
        log_result "PASS: Redis connection"
        return 0
    else
        print_failure "Redis connection failed"
        log_result "FAIL: Redis connection - Result: $result"
        return 1
    fi
}

# Function to test bot connectivity
test_bot_status() {
    ((TOTAL_TESTS++))
    print_header "Testing bot status"

    # Check if bot process is running
    local bot_running
    bot_running=$(docker-compose exec -T bot ps aux | grep -v grep | grep main.py | wc -l)

    if [[ $bot_running -gt 0 ]]; then
        print_success "Bot process is running"
        log_result "PASS: Bot process running"
        return 0
    else
        print_failure "Bot process is not running"
        log_result "FAIL: Bot process not running"
        return 1
    fi
}

# Function to test API endpoints
test_api_endpoints() {
    print_header "Testing API endpoints"

    # Test root endpoint
    ((TOTAL_TESTS++))
    if curl -f -s "$API_URL/" >/dev/null 2>&1; then
        print_success "API root endpoint accessible"
        log_result "PASS: API root endpoint"
    else
        print_failure "API root endpoint not accessible"
        log_result "FAIL: API root endpoint"
    fi

    # Test API info endpoint (if exists)
    ((TOTAL_TESTS++))
    if curl -f -s "$API_URL/api/v1/info" >/dev/null 2>&1; then
        print_success "API info endpoint accessible"
        log_result "PASS: API info endpoint"
    else
        print_warning "API info endpoint not accessible (may not exist)"
        log_result "WARN: API info endpoint not accessible"
    fi
}

# Function to test frontend
test_frontend() {
    ((TOTAL_TESTS++))
    print_header "Testing frontend accessibility"

    local response
    response=$(curl -s -I "$FRONTEND_URL" 2>/dev/null | head -1)

    if echo "$response" | grep -q "200\|301\|302"; then
        print_success "Frontend is accessible"
        log_result "PASS: Frontend accessible"
        return 0
    else
        print_failure "Frontend is not accessible"
        log_result "FAIL: Frontend not accessible - Response: $response"
        return 1
    fi
}

# Function to test Docker services
test_docker_services() {
    print_header "Testing Docker services"

    local services=("postgres" "redis" "api" "bot" "frontend")
    local failed_services=()

    for service in "${services[@]}"; do
        ((TOTAL_TESTS++))
        if docker-compose ps "$service" 2>/dev/null | grep -q "Up"; then
            print_success "$service container is running"
            log_result "PASS: $service container running"
        else
            print_failure "$service container is not running"
            log_result "FAIL: $service container not running"
            failed_services+=("$service")
        fi
    done

    if [[ ${#failed_services[@]} -gt 0 ]]; then
        return 1
    fi
}

# Function to test network connectivity between services
test_service_connectivity() {
    print_header "Testing service connectivity"

    # Test API to database connectivity
    ((TOTAL_TESTS++))
    local db_test
    db_test=$(docker-compose exec -T api python3 -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    conn.close()
    print('SUCCESS')
except Exception as e:
    print(f'FAILED: {e}')
" 2>/dev/null)

    if echo "$db_test" | grep -q "SUCCESS"; then
        print_success "API can connect to database"
        log_result "PASS: API to database connectivity"
    else
        print_failure "API cannot connect to database"
        log_result "FAIL: API to database connectivity - $db_test"
    fi

    # Test API to Redis connectivity
    ((TOTAL_TESTS++))
    local redis_test
    redis_test=$(docker-compose exec -T api python3 -c "
import redis
try:
    r = redis.Redis(host='redis', decode_responses=True)
    r.ping()
    print('SUCCESS')
except Exception as e:
    print(f'FAILED: {e}')
" 2>/dev/null)

    if echo "$redis_test" | grep -q "SUCCESS"; then
        print_success "API can connect to Redis"
        log_result "PASS: API to Redis connectivity"
    else
        print_failure "API cannot connect to Redis"
        log_result "FAIL: API to Redis connectivity - $redis_test"
    fi
}

# Function to run backend tests
run_backend_tests() {
    print_header "Running backend tests"

    # Test API unit tests
    ((TOTAL_TESTS++))
    if docker-compose exec -T api python -m pytest --tb=short 2>/dev/null; then
        print_success "API tests passed"
        log_result "PASS: API tests"
    else
        print_failure "API tests failed"
        log_result "FAIL: API tests"
    fi

    # Test bot unit tests
    ((TOTAL_TESTS++))
    if docker-compose exec -T bot python -m pytest --tb=short 2>/dev/null; then
        print_success "Bot tests passed"
        log_result "PASS: Bot tests"
    else
        print_failure "Bot tests failed"
        log_result "FAIL: Bot tests"
    fi
}

# Function to run frontend tests
run_frontend_tests() {
    print_header "Running frontend tests"

    ((TOTAL_TESTS++))
    if docker-compose exec -T frontend npm test -- --watchAll=false 2>/dev/null; then
        print_success "Frontend tests passed"
        log_result "PASS: Frontend tests"
    else
        print_failure "Frontend tests failed"
        log_result "FAIL: Frontend tests"
    fi
}

# Function to test performance
test_performance() {
    print_header "Testing performance"

    # Test API response time
    ((TOTAL_TESTS++))
    local start_time
    start_time=$(date +%s%N)
    curl -s "$API_URL/health" >/dev/null
    local end_time
    end_time=$(date +%s%N)
    local response_time=$(( (end_time - start_time) / 1000000 )) # Convert to milliseconds

    if [[ $response_time -lt 1000 ]]; then # Less than 1 second
        print_success "API response time: ${response_time}ms"
        log_result "PASS: API response time ${response_time}ms"
    else
        print_failure "API response time too slow: ${response_time}ms"
        log_result "FAIL: API response time ${response_time}ms"
    fi
}

# Function to generate test report
generate_report() {
    echo ""
    echo "=========================================="
    echo "TEST RESULTS SUMMARY"
    echo "=========================================="
    echo "Total Tests: $TOTAL_TESTS"
    echo "Passed: $PASSED_TESTS"
    echo "Failed: $FAILED_TESTS"
    echo "Success Rate: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%"
    echo ""
    echo "Detailed results saved to: $TEST_RESULTS"

    # Save summary to log file
    {
        echo "=========================================="
        echo "TEST RESULTS SUMMARY"
        echo "=========================================="
        echo "Total Tests: $TOTAL_TESTS"
        echo "Passed: $PASSED_TESTS"
        echo "Failed: $FAILED_TESTS"
        echo "Success Rate: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%"
        echo "Test completed at: $(date)"
    } >> "$TEST_RESULTS"
}

# Function to show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --all          Run all tests (default)"
    echo "  --services     Test only service availability"
    echo "  --connectivity Test service connectivity"
    echo "  --backend      Run backend unit tests"
    echo "  --frontend     Run frontend unit tests"
    echo "  --performance  Run performance tests"
    echo "  --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --all"
    echo "  $0 --services"
}

# Main execution
main() {
    local test_services=false
    local test_connectivity=false
    local test_backend=false
    local test_frontend=false
    local test_performance=false
    local run_all=true

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --services)
                test_services=true
                run_all=false
                shift
                ;;
            --connectivity)
                test_connectivity=true
                run_all=false
                shift
                ;;
            --backend)
                test_backend=true
                run_all=false
                shift
                ;;
            --frontend)
                test_frontend=true
                run_all=false
                shift
                ;;
            --performance)
                test_performance=true
                run_all=false
                shift
                ;;
            --help)
                usage
                exit 0
                ;;
            --all|*)
                run_all=true
                shift
                ;;
        esac
    done

    echo "Starting test suite..."
    echo "Results will be logged to: $TEST_RESULTS"
    echo ""

    # Initialize log file
    echo "Test Suite Started: $(date)" > "$TEST_RESULTS"
    echo "==========================================" >> "$TEST_RESULTS"

    if [[ $run_all == true ]] || [[ $test_services == true ]]; then
        # Basic service checks
        check_service "API" "$API_URL/health"
        check_service "Frontend" "$FRONTEND_URL"
        test_api_health
        test_database_connection
        test_redis_connection
        test_bot_status
        test_docker_services
    fi

    if [[ $run_all == true ]] || [[ $test_connectivity == true ]]; then
        test_service_connectivity
        test_api_endpoints
    fi

    if [[ $run_all == true ]] || [[ $test_backend == true ]]; then
        run_backend_tests
    fi

    if [[ $run_all == true ]] || [[ $test_frontend == true ]]; then
        run_frontend_tests
    fi

    if [[ $run_all == true ]] || [[ $test_performance == true ]]; then
        test_performance
    fi

    # Generate final report
    generate_report

    # Exit with appropriate code
    if [[ $FAILED_TESTS -gt 0 ]]; then
        print_failure "Test suite completed with $FAILED_TESTS failure(s)"
        exit 1
    else
        print_success "All tests passed!"
        exit 0
    fi
}

# Run main function
main "$@"