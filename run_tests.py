#!/usr/bin/env python3
"""
Test runner script for the Discord Bot Control Panel
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(command, cwd=None, env=None):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {command}")
        print(f"Error: {e.stderr}")
        return e.stdout, e.stderr, e.returncode

def setup_test_environment():
    """Set up the test environment."""
    print("Setting up test environment...")

    # Create test database if needed
    # This would be handled by docker-compose in production

    print("Test environment setup complete.")

def run_unit_tests():
    """Run unit tests."""
    print("Running unit tests...")

    cmd = "python -m pytest tests/ -v -m 'unit' --tb=short"
    stdout, stderr, returncode = run_command(cmd)

    if returncode == 0:
        print("✅ Unit tests passed!")
    else:
        print("❌ Unit tests failed!")
        print(stdout)
        print(stderr)

    return returncode == 0

def run_integration_tests():
    """Run integration tests."""
    print("Running integration tests...")

    cmd = "python -m pytest tests/ -v -m 'integration' --tb=short"
    stdout, stderr, returncode = run_command(cmd)

    if returncode == 0:
        print("✅ Integration tests passed!")
    else:
        print("❌ Integration tests failed!")
        print(stdout)
        print(stderr)

    return returncode == 0

def run_security_tests():
    """Run security tests."""
    print("Running security tests...")

    cmd = "python -m pytest tests/ -v -m 'security' --tb=short"
    stdout, stderr, returncode = run_command(cmd)

    if returncode == 0:
        print("✅ Security tests passed!")
    else:
        print("❌ Security tests failed!")
        print(stderr)

    return returncode == 0

def run_all_tests():
    """Run all tests."""
    print("Running all tests...")

    cmd = "python -m pytest tests/ -v --tb=short --cov=backend.api --cov-report=term-missing"
    stdout, stderr, returncode = run_command(cmd)

    if returncode == 0:
        print("✅ All tests passed!")
        print(stdout)
    else:
        print("❌ Some tests failed!")
        print(stdout)
        print(stderr)

    return returncode == 0

def run_coverage_report():
    """Generate coverage report."""
    print("Generating coverage report...")

    cmd = "python -m pytest tests/ --cov=backend.api --cov-report=html --cov-report=term-missing"
    stdout, stderr, returncode = run_command(cmd)

    if returncode == 0:
        print("✅ Coverage report generated!")
        print("HTML report available at: htmlcov/index.html")
        print(stdout)
    else:
        print("❌ Coverage report generation failed!")
        print(stderr)

    return returncode == 0

def run_linting():
    """Run code linting."""
    print("Running code linting...")

    # Run flake8
    cmd = "python -m flake8 backend/ --max-line-length=100 --extend-ignore=E203,W503"
    stdout, stderr, returncode = run_command(cmd)

    if returncode == 0:
        print("✅ Linting passed!")
    else:
        print("❌ Linting failed!")
        print(stderr)

    return returncode == 0

def run_type_checking():
    """Run type checking with mypy."""
    print("Running type checking...")

    cmd = "python -m mypy backend/api/ --ignore-missing-imports"
    stdout, stderr, returncode = run_command(cmd)

    if returncode == 0:
        print("✅ Type checking passed!")
    else:
        print("❌ Type checking failed!")
        print(stderr)

    return returncode == 0

def run_security_scan():
    """Run security scanning with bandit."""
    print("Running security scan...")

    cmd = "python -m bandit -r backend/ -f json -o security_report.json"
    stdout, stderr, returncode = run_command(cmd)

    if returncode == 0:
        print("✅ Security scan completed!")
        print("Report saved to: security_report.json")
    else:
        print("❌ Security scan failed!")
        print(stderr)

    return returncode == 0

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test runner for Discord Bot Control Panel')
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--security', action='store_true', help='Run security tests only')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--lint', action='store_true', help='Run linting')
    parser.add_argument('--type-check', action='store_true', help='Run type checking')
    parser.add_argument('--security-scan', action='store_true', help='Run security scan')
    parser.add_argument('--all', action='store_true', help='Run all tests and checks')

    args = parser.parse_args()

    # Change to project root directory
    project_root = Path(__file__).parent
    os.chdir(project_root)

    # Setup test environment
    setup_test_environment()

    results = []

    if args.all or not any([args.unit, args.integration, args.security, args.coverage, args.lint, args.type_check, args.security_scan]):
        # Run all tests and checks
        results.append(("Unit Tests", run_unit_tests()))
        results.append(("Integration Tests", run_integration_tests()))
        results.append(("Security Tests", run_security_tests()))
        results.append(("Coverage Report", run_coverage_report()))
        results.append(("Linting", run_linting()))
        results.append(("Type Checking", run_type_checking()))
        results.append(("Security Scan", run_security_scan()))
    else:
        # Run specific tests/checks
        if args.unit:
            results.append(("Unit Tests", run_unit_tests()))
        if args.integration:
            results.append(("Integration Tests", run_integration_tests()))
        if args.security:
            results.append(("Security Tests", run_security_tests()))
        if args.coverage:
            results.append(("Coverage Report", run_coverage_report()))
        if args.lint:
            results.append(("Linting", run_linting()))
        if args.type_check:
            results.append(("Type Checking", run_type_checking()))
        if args.security_scan:
            results.append(("Security Scan", run_security_scan()))

    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print("25")
        if not passed:
            all_passed = False

    print("\nOverall Result:", "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED")

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()