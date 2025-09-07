#!/usr/bin/env python3
"""
Deployment Verification Script
Tests the complete Discord Bot Control Panel stack
"""
import os
import sys
import time
import requests
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DeploymentVerifier:
    """Comprehensive deployment verification"""

    def __init__(self, base_url: str = "http://localhost"):
        self.base_url = base_url
        self.api_url = f"{base_url}:5000"
        self.frontend_url = f"{base_url}:3000"
        self.results = []
        self.errors = []

    def log_result(self, test_name: str, success: bool, message: str = "", details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} - {test_name}: {message}")

        if details:
            logger.info(f"   Details: {details}")

        self.results.append({
            'test': test_name,
            'success': success,
            'message': message,
            'details': details
        })

        if not success:
            self.errors.append(f"{test_name}: {message}")

    def run_command(self, command: str, cwd: Optional[str] = None) -> Tuple[str, str, int]:
        """Run shell command and return results"""
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=30
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", 1
        except Exception as e:
            return "", str(e), 1

    def test_docker_services(self) -> bool:
        """Test Docker services are running"""
        logger.info("Testing Docker services...")

        stdout, stderr, returncode = self.run_command("docker-compose ps")

        if returncode != 0:
            self.log_result("Docker Services", False, "Failed to get service status", stderr)
            return False

        # Check for expected services
        expected_services = ['postgres', 'api', 'bot', 'frontend']
        running_services = []

        for line in stdout.split('\n'):
            if any(service in line for service in expected_services):
                parts = line.split()
                if len(parts) >= 4 and parts[3] == 'Up':
                    service_name = parts[0].split('_')[-1]  # Extract service name
                    running_services.append(service_name)

        success = len(running_services) >= len(expected_services)
        self.log_result(
            "Docker Services",
            success,
            f"Running services: {', '.join(running_services)}",
            f"Expected: {', '.join(expected_services)}"
        )
        return success

    def test_database_connectivity(self) -> bool:
        """Test database connectivity"""
        logger.info("Testing database connectivity...")

        # Test PostgreSQL connection
        stdout, stderr, returncode = self.run_command(
            "docker-compose exec postgres pg_isready -U discord_bot_user -d discord_bot_platform"
        )

        if returncode == 0:
            self.log_result("Database Connectivity", True, "PostgreSQL is ready")
            return True
        else:
            self.log_result("Database Connectivity", False, "PostgreSQL connection failed", stderr)
            return False

    def test_api_health(self) -> bool:
        """Test API health endpoint"""
        logger.info("Testing API health...")

        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    self.log_result("API Health", True, "API is healthy")
                    return True
                else:
                    self.log_result("API Health", False, f"API returned unhealthy status: {data}")
                    return False
            else:
                self.log_result("API Health", False, f"API returned status {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            self.log_result("API Health", False, f"API request failed: {str(e)}")
            return False

    def test_api_endpoints(self) -> bool:
        """Test key API endpoints"""
        logger.info("Testing API endpoints...")

        endpoints = [
            ('/api/v1/embeds/templates', 'GET'),
            ('/api/v1/stats/messages', 'GET'),
            ('/api/v1/giveaways', 'GET'),
            ('/api/v1/media/search/movies?query=test', 'GET'),
        ]

        success_count = 0

        for endpoint, method in endpoints:
            try:
                if method == 'GET':
                    response = requests.get(f"{self.api_url}{endpoint}", timeout=10)

                # Accept 401 (unauthorized) as success since we don't have auth tokens
                if response.status_code in [200, 401, 403]:
                    success_count += 1
                else:
                    logger.warning(f"Endpoint {endpoint} returned {response.status_code}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"Endpoint {endpoint} failed: {str(e)}")

        success = success_count >= len(endpoints) * 0.8  # 80% success rate
        self.log_result(
            "API Endpoints",
            success,
            f"{success_count}/{len(endpoints)} endpoints accessible"
        )
        return success

    def test_frontend_accessibility(self) -> bool:
        """Test frontend accessibility"""
        logger.info("Testing frontend accessibility...")

        try:
            response = requests.get(self.frontend_url, timeout=10)

            if response.status_code == 200:
                if 'Discord Bot Control Panel' in response.text:
                    self.log_result("Frontend Accessibility", True, "Frontend is accessible")
                    return True
                else:
                    self.log_result("Frontend Accessibility", False, "Frontend content not found")
                    return False
            else:
                self.log_result("Frontend Accessibility", False, f"Frontend returned {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            self.log_result("Frontend Accessibility", False, f"Frontend request failed: {str(e)}")
            return False

    def test_bot_logs(self) -> bool:
        """Test bot is running and logging"""
        logger.info("Testing bot logs...")

        stdout, stderr, returncode = self.run_command("docker-compose logs bot --tail=20")

        if returncode == 0:
            # Check for signs of bot activity
            log_content = stdout.lower()
            success_indicators = ['ready', 'connected', 'logged in', 'command']

            if any(indicator in log_content for indicator in success_indicators):
                self.log_result("Bot Logs", True, "Bot appears to be running")
                return True
            elif 'error' in log_content or 'exception' in log_content:
                self.log_result("Bot Logs", False, "Bot has errors in logs")
                return False
            else:
                self.log_result("Bot Logs", True, "Bot logs show activity (unclear status)")
                return True
        else:
            self.log_result("Bot Logs", False, "Failed to get bot logs", stderr)
            return False

    def test_network_connectivity(self) -> bool:
        """Test network connectivity between services"""
        logger.info("Testing network connectivity...")

        # Test API to database connectivity (via health check)
        try:
            response = requests.get(f"{self.api_url}/health/detailed", timeout=10)

            if response.status_code == 200:
                data = response.json()
                checks = data.get('checks', {})

                # Check if database check exists and is healthy
                db_check = None
                for check_name, check_data in checks.items():
                    if 'database' in check_name.lower():
                        db_check = check_data
                        break

                if db_check and db_check.get('status') == 'healthy':
                    self.log_result("Network Connectivity", True, "Services can communicate")
                    return True
                else:
                    self.log_result("Network Connectivity", False, "Database connectivity issue")
                    return False
            else:
                self.log_result("Network Connectivity", False, "Detailed health check failed")
                return False

        except requests.exceptions.RequestException as e:
            self.log_result("Network Connectivity", False, f"Network test failed: {str(e)}")
            return False

    def test_configuration(self) -> bool:
        """Test configuration files"""
        logger.info("Testing configuration...")

        config_files = [
            '.env',
            'docker-compose.yml',
            'backend/api/requirements.txt',
            'backend/bot/requirements.txt',
            'frontend/package.json'
        ]

        missing_files = []
        for config_file in config_files:
            if not Path(config_file).exists():
                missing_files.append(config_file)

        if not missing_files:
            self.log_result("Configuration", True, "All configuration files present")
            return True
        else:
            self.log_result("Configuration", False, f"Missing files: {', '.join(missing_files)}")
            return False

    def test_environment_variables(self) -> bool:
        """Test environment variables are set"""
        logger.info("Testing environment variables...")

        required_vars = [
            'DISCORD_BOT_TOKEN',
            'DISCORD_CLIENT_ID',
            'DISCORD_CLIENT_SECRET',
            'DATABASE_URL'
        ]

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if not missing_vars:
            self.log_result("Environment Variables", True, "Required variables are set")
            return True
        else:
            self.log_result("Environment Variables", False, f"Missing variables: {', '.join(missing_vars)}")
            return False

    def run_full_verification(self) -> bool:
        """Run complete verification suite"""
        logger.info("Starting full deployment verification...")

        tests = [
            ("Docker Services", self.test_docker_services),
            ("Database Connectivity", self.test_database_connectivity),
            ("API Health", self.test_api_health),
            ("API Endpoints", self.test_api_endpoints),
            ("Frontend Accessibility", self.test_frontend_accessibility),
            ("Bot Logs", self.test_bot_logs),
            ("Network Connectivity", self.test_network_connectivity),
            ("Configuration", self.test_configuration),
            ("Environment Variables", self.test_environment_variables),
        ]

        passed_tests = 0
        total_tests = len(tests)

        for test_name, test_func in tests:
            logger.info(f"Running: {test_name}")
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                self.log_result(test_name, False, f"Test failed with exception: {str(e)}")
                logger.error(f"Test {test_name} failed with exception: {str(e)}")

        # Summary
        success_rate = (passed_tests / total_tests) * 100
        overall_success = success_rate >= 80  # 80% success threshold

        logger.info(f"\n{'='*50}")
        logger.info("VERIFICATION SUMMARY")
        logger.info(f"{'='*50}")
        logger.info(f"Passed: {passed_tests}/{total_tests} tests ({success_rate:.1f}%)")

        if overall_success:
            logger.info("✅ DEPLOYMENT VERIFICATION PASSED")
        else:
            logger.info("❌ DEPLOYMENT VERIFICATION FAILED")

        if self.errors:
            logger.info("\nErrors encountered:")
            for error in self.errors:
                logger.info(f"  - {error}")

        return overall_success

    def generate_report(self) -> str:
        """Generate verification report"""
        report = []
        report.append("# Deployment Verification Report")
        report.append("")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
        report.append("")

        # Summary
        passed = sum(1 for r in self.results if r['success'])
        total = len(self.results)
        success_rate = (passed / total * 100) if total > 0 else 0

        report.append("## Summary")
        report.append(f"- **Tests Passed**: {passed}/{total} ({success_rate:.1f}%)")
        report.append(f"- **Overall Status**: {'✅ PASSED' if success_rate >= 80 else '❌ FAILED'}")
        report.append("")

        # Detailed Results
        report.append("## Test Results")
        report.append("")
        for result in self.results:
            status = "✅" if result['success'] else "❌"
            report.append(f"### {status} {result['test']}")
            report.append(f"**Status**: {'PASSED' if result['success'] else 'FAILED'}")
            if result['message']:
                report.append(f"**Message**: {result['message']}")
            if result['details']:
                report.append(f"**Details**: {result['details']}")
            report.append("")

        # Errors
        if self.errors:
            report.append("## Errors")
            report.append("")
            for error in self.errors:
                report.append(f"- {error}")
            report.append("")

        # Recommendations
        report.append("## Recommendations")
        report.append("")
        if success_rate < 80:
            report.append("### Critical Issues")
            report.append("- Address failed tests before proceeding to production")
            report.append("- Check logs for detailed error information")
            report.append("- Verify configuration files and environment variables")
            report.append("")
        else:
            report.append("### Next Steps")
            report.append("- Monitor application logs for runtime issues")
            report.append("- Set up monitoring and alerting")
            report.append("- Configure backup procedures")
            report.append("")

        return "\n".join(report)


def main():
    """Main verification function"""
    import argparse

    parser = argparse.ArgumentParser(description='Verify Discord Bot Control Panel deployment')
    parser.add_argument('--url', default='http://localhost', help='Base URL for verification')
    parser.add_argument('--report', action='store_true', help='Generate detailed report')
    parser.add_argument('--output', default='verification_report.md', help='Report output file')

    args = parser.parse_args()

    verifier = DeploymentVerifier(args.url)

    logger.info("Discord Bot Control Panel - Deployment Verification")
    logger.info("=" * 60)

    success = verifier.run_full_verification()

    if args.report:
        report = verifier.generate_report()
        with open(args.output, 'w') as f:
            f.write(report)
        logger.info(f"Report saved to: {args.output}")

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()