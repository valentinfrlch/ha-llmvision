# Testing Guide for LLM Vision

This guide provides instructions for setting up the testing environment, running tests, and debugging issues.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Setting Up the Virtual Environment](#setting-up-the-virtual-environment)
- [Running Tests](#running-tests)
- [Coverage Reports](#coverage-reports)
- [Debugging Tests](#debugging-tests)
- [Writing New Tests](#writing-new-tests)
- [Common Issues and Solutions](#common-issues-and-solutions)

## Prerequisites

- Python 3.13
- pip (Python package installer)
- Git (for cloning the repository)

## Setting Up the Virtual Environment

### 1. Create a Virtual Environment

```bash
# Navigate to the project root directory
cd ha-llmvision

# Create a virtual environment
python -m venv .venv
```

### 2. Activate the Virtual Environment

**On macOS/Linux:**
```bash
source .venv/bin/activate
```

**On Windows:**
```cmd
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install all test dependencies from requirements file
pip install -r requirements-test.txt
```

**Note:** The `requirements-test.txt` file includes all necessary dependencies for running tests, including:
- Testing frameworks (pytest and plugins)
- Home Assistant testing utilities
- Mocking libraries
- Code coverage tools
- Component dependencies (aiohttp, Pillow, etc.)

### 4. Python Path Configuration

The project includes a `pytest.ini` file that automatically configures the Python path, so tests should work out of the box. If you encounter import errors, you can manually set the PYTHONPATH:

```bash
# Add project root to PYTHONPATH (if needed)
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

The `pytest.ini` file also configures:
- Test discovery patterns
- Default pytest options (verbose, no cache files)
- Coverage settings
- Test markers for categorization

**Note:** The project is configured to not create `.pytest_cache` directories to keep the repository clean. All test artifacts are listed in `.gitignore`.

### 5. Verify Installation

```bash
# Check pytest is installed
pytest --version
# Should output something like: pytest 8.4.2

# Verify Python path is configured correctly
python -c "import sys; print('custom_components' in str(sys.path))"

# Run a simple test to verify everything works
pytest tests/test_const.py::TestConstants::test_domain -v
```

## Running Tests

### Run All Tests

```bash
# Run all unit tests (default - excludes integration tests)
pytest tests/ -v

# Run only unit tests (explicitly exclude integration tests)
pytest tests/ -m "not integration" -v

# Run ALL tests including integration tests (requires setup)
pytest tests/ -v --run-integration
```

**Note:** Integration tests in `tests/test_api.py` are automatically skipped unless you have the required configuration files (`.instance` and `.token`).

### Run Specific Test Files

```bash
# Run tests for a specific module
pytest tests/test_memory.py -v

# Run tests for multiple modules
pytest tests/test_memory.py tests/test_calendar.py -v
```

### Run Specific Test Classes or Functions

```bash
# Run a specific test class
pytest tests/test_memory.py::TestMemory -v

# Run a specific test function
pytest tests/test_memory.py::TestMemory::test_init_without_entry -v
```

### Run Tests with Different Output Formats

```bash
# Quiet mode (less verbose)
pytest tests/ -q

# Show print statements
pytest tests/ -v -s

# Stop on first failure
pytest tests/ -x

# Show local variables on failure
pytest tests/ -l
```

## Coverage Reports

### Generate Coverage Report

```bash
# Run tests with coverage
pytest tests/ --ignore=tests/test_api.py --cov=custom_components/llmvision --cov-report=term

# Generate HTML coverage report
pytest tests/ --ignore=tests/test_api.py --cov=custom_components/llmvision --cov-report=html

# View HTML report (opens in browser)
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage Report Options

```bash
# Show missing lines in terminal
pytest tests/ --cov=custom_components/llmvision --cov-report=term-missing

# Generate multiple report formats
pytest tests/ --cov=custom_components/llmvision --cov-report=term --cov-report=html --cov-report=xml

# Set minimum coverage threshold (fails if below)
pytest tests/ --cov=custom_components/llmvision --cov-fail-under=50
```

## Debugging Tests

### Using pytest Debugging Features

```bash
# Drop into debugger on failure
pytest tests/ --pdb

# Drop into debugger at start of each test
pytest tests/ --trace

# Show captured output even for passing tests
pytest tests/ -v -s
```

### Using Python Debugger (pdb)

Add breakpoints in your test code:

```python
def test_something():
    import pdb; pdb.set_trace()  # Breakpoint
    # Your test code here
```

### Debugging with VS Code

Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Pytest Current File",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "args": [
                "${file}",
                "-v",
                "-s"
            ],
            "console": "integratedTerminal",
            "justMyCode": false
        }
    ]
}
```

### Verbose Logging

```bash
# Show all log output
pytest tests/ -v --log-cli-level=DEBUG

# Show warnings
pytest tests/ -v -W all
```

## Writing New Tests

### Test File Structure

```python
"""Unit tests for module_name.py module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock


class TestClassName:
    """Test ClassName class."""

    @pytest.fixture
    def mock_dependency(self):
        """Create a mock dependency."""
        return Mock()

    def test_method_name(self, mock_dependency):
        """Test method_name does something."""
        # Arrange
        instance = ClassName(mock_dependency)
        
        # Act
        result = instance.method_name()
        
        # Assert
        assert result == expected_value

    @pytest.mark.asyncio
    async def test_async_method(self):
        """Test async method."""
        result = await async_function()
        assert result is not None
```

### Best Practices

1. **Use descriptive test names**: `test_method_name_when_condition_then_expected_result`
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **One assertion per test** (when possible)
4. **Use fixtures** for common setup
5. **Mock external dependencies** (API calls, database, file system)
6. **Test edge cases** (empty inputs, None values, errors)
7. **Keep tests independent** (no shared state between tests)

### Common Fixtures

Available in `tests/conftest.py`:

```python
@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    
@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
```

## Common Issues and Solutions

### Issue: Import Errors

**Problem:** `ModuleNotFoundError: No module named 'custom_components'` or missing test dependencies

**Solution:**
```bash
# Ensure you're in the project root directory
cd ha-llmvision

# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall all test dependencies
pip install -r requirements-test.txt

# If still having issues, try upgrading pip first
pip install --upgrade pip
pip install -r requirements-test.txt
```

### Issue: Async Tests Not Running

**Problem:** `RuntimeWarning: coroutine was never awaited`

**Solution:**
```python
# Add @pytest.mark.asyncio decorator
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

### Issue: Mock Not Working

**Problem:** Mock is not being used, real code is executing

**Solution:**
```python
# Ensure you're patching the right location
# Patch where it's used, not where it's defined
with patch('module_using_function.function_name') as mock_func:
    # Your test code
```

### Issue: Tests Pass Individually But Fail Together

**Problem:** Tests have shared state or side effects

**Solution:**
```python
# Use fixtures with proper scope
@pytest.fixture(scope="function")  # Creates new instance per test
def my_fixture():
    return SomeObject()

# Or use autouse fixtures to clean up
@pytest.fixture(autouse=True)
def cleanup():
    yield
    # Cleanup code here
```

### Issue: Coverage Not Showing All Files

**Problem:** Some modules not included in coverage report

**Solution:**
```bash
# Specify the package explicitly
pytest tests/ --cov=custom_components/llmvision --cov-report=term-missing

# Or create .coveragerc file
[run]
source = custom_components/llmvision
omit = 
    */tests/*
    */__pycache__/*
```

### Issue: Tests Running Slowly

**Problem:** Tests take too long to execute

**Solution:**
```bash
# Run tests in parallel (pytest-xdist is included in requirements-test.txt)
pytest tests/ -n auto  # Uses all CPU cores

# Run only failed tests from last run
pytest tests/ --lf

# Run tests that failed first, then others
pytest tests/ --ff

# Skip slow tests (if marked with @pytest.mark.slow)
pytest tests/ -m "not slow"
```

## Continuous Integration

The project includes a GitHub Actions workflow (`.github/workflows/tests.yaml`) that automatically runs tests on:
- Push to main/master/dev branches
- Pull requests
- Manual workflow dispatch

### What the CI Does

1. **Matrix Testing**: Tests run on Python
2. **Unit Tests**: Runs all unit tests (excludes integration tests)
3. **Coverage Report**: Generates coverage report and uploads to Codecov
4. **Test Summary**: Provides a summary of test results

### Viewing Test Results

- Check the "Actions" tab in your GitHub repository
- Each commit/PR will show test status with a ✅ or ❌
- Click on a workflow run to see detailed test output
- Coverage reports are available on Codecov (if configured)

### Local Testing Before Push

Always run tests locally before pushing:

```bash
# Quick test
pytest tests/ -m "not integration" -q

# Full test with coverage (like CI)
pytest tests/ -m "not integration" --cov=custom_components/llmvision --cov-report=term
```

## Project Configuration Files

The project includes several configuration files for testing:

- **`pytest.ini`** - Main pytest configuration
  - Configures Python path automatically
  - Sets default test options
  - Defines test markers (slow, integration, unit)
  - Configures coverage settings

- **`requirements-test.txt`** - All testing dependencies
  - Testing frameworks and plugins
  - Home Assistant testing utilities
  - Mocking and coverage tools

- **`.coveragerc`** (optional) - Additional coverage configuration
  - Can be used to override pytest.ini coverage settings

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Home Assistant Testing](https://developers.home-assistant.io/docs/development_testing)

## Test Types

### Unit Tests
Located in `tests/test_*.py` files (except `test_api.py`). These test individual components in isolation using mocks and don't require external dependencies.

**Run unit tests:**
```bash
pytest tests/ -m "not integration" -v
```

### Integration Tests
Located in `tests/test_api.py`. These test the actual API endpoints against a running Home Assistant instance.

**Setup for integration tests:**
1. Start a Home Assistant instance
2. Create `tests/.instance` with your HA URL:
   ```
   http://localhost:8123
   ```
3. Create `tests/.token` with a long-lived access token
4. Run integration tests:
   ```bash
   pytest tests/test_api.py -v
   ```

**Note:** Integration tests are automatically skipped if configuration files are missing.

## Current Test Statistics

- **Total Unit Tests:** 143
- **Overall Coverage:** 25%
- **Modules with High Coverage:**
  - `const.py`: 100%
  - `calendar.py`: 96%
  - `memory.py`: 77%

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure all tests pass: `pytest tests/ -v`
3. Check coverage: `pytest tests/ --cov=custom_components/llmvision`
4. Aim for at least 80% coverage on new code
5. Update this README if adding new test patterns

## Getting Help

If you encounter issues:

1. Check the [Common Issues](#common-issues-and-solutions) section
2. Run tests with verbose output: `pytest tests/ -vv`
3. Check the HTML coverage report for uncovered lines
4. Review test logs: `pytest tests/ --log-cli-level=DEBUG`


## Quick Start Guide

For those who want to get started quickly:

```bash
# 1. Clone the repository (if not already done)
git clone <repository-url>
cd ha-llmvision

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install all test dependencies
pip install -r requirements-test.txt

# 4. Run tests using the convenience script
./run_tests.sh              # Run all unit tests
./run_tests.sh -c           # Run with coverage report
./run_tests.sh -q           # Quick run (quiet mode)

# Or use pytest directly
pytest tests/ -v            # Run all tests (integration tests auto-skipped)
pytest tests/ -m "not integration" --cov=custom_components/llmvision --cov-report=html
```

That's it! You're ready to run tests and contribute to the project.

### Test Script Options

The `run_tests.sh` script provides convenient shortcuts:

```bash
./run_tests.sh              # Run all unit tests
./run_tests.sh -c           # Run with coverage report
./run_tests.sh -v           # Verbose output
./run_tests.sh -q           # Quick/quiet mode
./run_tests.sh -i           # Include integration tests
./run_tests.sh -c -v        # Coverage with verbose output
./run_tests.sh --help       # Show all options
```


## Command Reference Cheat Sheet

### Setup Commands
```bash
python -m venv .venv                    # Create virtual environment
source .venv/bin/activate               # Activate (macOS/Linux)
.venv\Scripts\activate                  # Activate (Windows)
pip install -r requirements-test.txt    # Install dependencies
```

### Running Tests (Using Script)
```bash
./run_tests.sh                          # Run all unit tests
./run_tests.sh -c                       # Run with coverage
./run_tests.sh -v                       # Verbose output
./run_tests.sh -q                       # Quick/quiet mode
./run_tests.sh -i                       # Include integration tests
./run_tests.sh --help                   # Show all options
```

### Running Tests (Using pytest directly)
```bash
pytest tests/ -v                        # Run all tests (verbose)
pytest tests/ -q                        # Run all tests (quiet)
pytest tests/test_memory.py             # Run specific file
pytest tests/ -k "test_init"            # Run tests matching pattern
pytest tests/ -x                        # Stop on first failure
pytest tests/ --lf                      # Run last failed tests
pytest tests/ -n auto                   # Run tests in parallel
pytest tests/ -m "not integration"      # Exclude integration tests
```

### Coverage Commands
```bash
pytest tests/ --cov=custom_components/llmvision                    # Basic coverage
pytest tests/ --cov=custom_components/llmvision --cov-report=html  # HTML report
pytest tests/ --cov=custom_components/llmvision --cov-report=term-missing  # Show missing lines
open htmlcov/index.html                                            # View HTML report
```

### Debugging Commands
```bash
pytest tests/ --pdb                     # Drop into debugger on failure
pytest tests/ -vv -s                    # Very verbose with print output
pytest tests/ --log-cli-level=DEBUG     # Show debug logs
pytest tests/ -l                        # Show local variables on failure
```

### Useful Combinations
```bash
# Run specific test with coverage and verbose output
pytest tests/test_memory.py::TestMemory::test_init_without_entry -v --cov=custom_components/llmvision

# Run all tests except integration tests with coverage
pytest tests/ --ignore=tests/test_api.py --cov=custom_components/llmvision --cov-report=html

# Run failed tests first, stop on first failure, show output
pytest tests/ --ff -x -s
```

## Maintenance

### Updating Test Dependencies

```bash
# Update all dependencies to latest versions
pip install --upgrade -r requirements-test.txt

# Update specific package
pip install --upgrade pytest

# Check for outdated packages
pip list --outdated

# Freeze current versions (for reproducibility)
pip freeze > requirements-test-frozen.txt
```

### Cleaning Up

```bash
# Remove virtual environment
deactivate
rm -rf .venv

# Remove coverage files (if generated with --cov-report=html)
rm -rf .coverage htmlcov/

# Remove Python cache files
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

**Note:** The project is configured to not create `.pytest_cache` files automatically. Coverage HTML reports are only generated when explicitly requested with `--cov-report=html`.
