#!/bin/bash
# Convenience script for running tests
# Usage: ./run_tests.sh [options]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo -e "${YELLOW}Virtual environment not activated. Activating .venv...${NC}"
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        echo -e "${RED}Error: .venv directory not found. Run: python -m venv .venv${NC}"
        exit 1
    fi
fi

# Parse command line arguments
COVERAGE=false
VERBOSE=false
QUICK=false
INTEGRATION=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -q|--quick)
            QUICK=true
            shift
            ;;
        -i|--integration)
            INTEGRATION=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./run_tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  -c, --coverage     Run with coverage report"
            echo "  -v, --verbose      Verbose output"
            echo "  -q, --quick        Quick run (quiet mode)"
            echo "  -i, --integration  Include integration tests"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run_tests.sh                    # Run all unit tests"
            echo "  ./run_tests.sh -c                 # Run with coverage"
            echo "  ./run_tests.sh -q                 # Quick run"
            echo "  ./run_tests.sh -c -v              # Coverage with verbose output"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="pytest tests/"

if [ "$INTEGRATION" = false ]; then
    PYTEST_CMD="$PYTEST_CMD -m 'not integration'"
fi

if [ "$QUICK" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -q"
elif [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=custom_components/llmvision --cov-report=term --cov-report=html"
fi

# Run tests
echo -e "${GREEN}Running tests...${NC}"
echo "Command: $PYTEST_CMD"
echo ""

if eval $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
    
    if [ "$COVERAGE" = true ]; then
        echo -e "${GREEN}📊 Coverage report generated in htmlcov/index.html${NC}"
    fi
    exit 0
else
    echo ""
    echo -e "${RED}❌ Tests failed!${NC}"
    exit 1
fi
