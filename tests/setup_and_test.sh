#!/bin/bash
# Comprehensive test setup and runner for LLM Vision
# Handles fresh installs, existing venvs, and venv refresh scenarios

set -e

echo "🚀 LLM Vision Test Setup & Runner"
echo "=================================="
echo ""

# Ensure we're in the tests directory
cd "$(dirname "$0")"

# Function to check Python version
check_python() {
    echo "🐍 Checking Python version..."
    if command -v python3 &> /dev/null; then
        python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        echo "   Found Python $python_version"
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
            echo "   ✅ Python version is compatible (>= 3.9)"
            return 0
        else
            echo "   ❌ Python version too old. Need >= 3.9"
            exit 1
        fi
    else
        echo "   ❌ Python3 not found. Please install Python 3.9+"
        exit 1
    fi
}

# Function to check if venv needs refresh
check_venv_freshness() {
    if [ -d "venv" ]; then
        echo "🔍 Checking virtual environment freshness..."

        # Check if venv has Home Assistant
        if [ -f "venv/lib/python*/site-packages/homeassistant/__init__.py" ] || [ -f "venv/lib/python*/site-packages/homeassistant/__init__.py" ]; then
            echo "   ✅ Virtual environment appears to have Home Assistant"

            # Check if it's older than 30 days
            if [ $(find venv -mtime +30 | wc -l) -gt 0 ]; then
                echo "   ⚠️  Virtual environment is older than 30 days"
                read -p "   Refresh virtual environment? (y/N): " refresh_choice
                if [[ $refresh_choice =~ ^[Yy]$ ]]; then
                    return 1  # Needs refresh
                fi
            fi
            return 0  # Good to use
        else
            echo "   ❌ Virtual environment missing Home Assistant dependencies"
            return 1  # Needs refresh
        fi
    else
        echo "📦 No virtual environment found"
        return 1  # Needs creation
    fi
}

# Function to create/refresh virtual environment
setup_venv() {
    echo "🔧 Setting up virtual environment..."

    # Remove old venv if it exists
    if [ -d "venv" ]; then
        echo "   Removing old virtual environment..."
        rm -rf venv
    fi

    # Create new venv
    echo "   Creating new virtual environment..."
    python3 -m venv venv

    # Activate venv
    echo "   Activating virtual environment..."
    source venv/bin/activate

    # Upgrade pip
    echo "   Upgrading pip..."
    pip install --upgrade pip

    # Install core dependencies
    echo "   Installing core test dependencies..."
    pip install pytest pytest-asyncio aiohttp

    # Install Home Assistant (latest stable)
    echo "   Installing Home Assistant (this may take a few minutes)..."
    pip install homeassistant

    # Install additional dependencies that might be needed
    echo "   Installing additional dependencies..."
    pip install pillow boto3 openai anthropic google-generativeai aiosqlite aiofile numpy tenacity

    echo "   ✅ Virtual environment setup complete"
    deactivate
}

# Function to setup test secrets
setup_secrets() {
    if [ ! -f "test_secrets.py" ]; then
        echo "🔑 Setting up test secrets..."
        if [ -f "test_secrets.py.template" ]; then
            cp test_secrets.py.template test_secrets.py
            echo "   📋 Copied test_secrets.py.template to test_secrets.py"
            echo "   ⚠️  Please edit test_secrets.py and add your API keys"
            echo "   💡 You can run tests without API keys - they'll be skipped"
        else
            echo "   ⚠️  No test_secrets.py.template found, creating basic template..."
            cat > test_secrets.py << 'EOF'
# Test API Keys
# Add your API keys here to run integration tests
# Tests will be skipped if keys are not provided

# OpenAI API Key
OPENAI_API_KEY = ""

# Anthropic API Key
ANTHROPIC_API_KEY = ""

# Google API Key
GOOGLE_API_KEY = ""

# AWS Credentials (optional)
AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""
AWS_REGION = "us-east-1"

# Azure OpenAI (optional)
AZURE_OPENAI_API_KEY = ""
AZURE_OPENAI_ENDPOINT = ""
AZURE_OPENAI_DEPLOYMENT = ""

# Groq API Key (optional)
GROQ_API_KEY = ""
EOF
            echo "   📝 Created basic test_secrets.py template"
        fi
    else
        echo "🔑 test_secrets.py already exists"
    fi
}

# Function to run tests
run_tests() {
    echo "🧪 Running Tests"
    echo "==============="

    # Check if we have any API keys
    source venv/bin/activate
    python3 -c "
import sys
sys.path.append('.')
try:
    import test_secrets
    keys = []
    if getattr(test_secrets, 'OPENAI_API_KEY', '').strip(): keys.append('OpenAI')
    if getattr(test_secrets, 'ANTHROPIC_API_KEY', '').strip(): keys.append('Anthropic')
    if getattr(test_secrets, 'GOOGLE_API_KEY', '').strip(): keys.append('Google')

    if keys:
        print(f'🔑 Found API keys for: {', '.join(keys)}')
        print('   Will run integration tests for these providers')
    else:
        print('⚠️  No API keys found in test_secrets.py')
        print('   Integration tests will be skipped')
except ImportError:
    print('⚠️  test_secrets.py not found, integration tests will be skipped')
"

    echo ""
    echo "🏃 Running structured output integration tests..."

    # Run tests for available providers
    providers=("openai" "anthropic" "google" "ollama" "azureopenai" "groq" "localai" "bedrock")
    passed=0
    failed=0
    skipped=0

    for provider in "${providers[@]}"; do
        echo ""
        echo "Testing $provider..."
        if python3 ../tests/integration/test_structured_output_integration.py $provider 2>&1; then
            echo "✅ $provider: PASSED"
            ((passed++))
        else
            if [[ $? -eq 77 ]]; then  # pytest skip code
                echo "⏭️  $provider: SKIPPED (no API key or server not available)"
                ((skipped++))
            else
                echo "❌ $provider: FAILED"
                ((failed++))
            fi
        fi
    done

    deactivate

    echo ""
    echo "================================================"
    echo "Test Results Summary:"
    echo "  ✅ Passed: $passed"
    echo "  ❌ Failed: $failed"
    echo "  ⏭️  Skipped: $skipped"
    echo "================================================"

    if [ $failed -eq 0 ]; then
        echo "🎉 All tests completed successfully!"
        return 0
    else
        echo "💥 Some tests failed!"
        return 1
    fi
}

# Main execution
main() {
    check_python

    if check_venv_freshness; then
        echo "✅ Using existing virtual environment"
    else
        setup_venv
    fi

    setup_secrets

    echo ""
    read -p "🚀 Run tests now? (Y/n): " run_choice
    if [[ ! $run_choice =~ ^[Nn]$ ]]; then
        run_tests
    else
        echo "💡 Setup complete! Run this script again to execute tests."
        echo "💡 Or manually activate venv: source tests/venv/bin/activate"
    fi
}

# Handle command line arguments
case "${1:-}" in
    --force-refresh)
        echo "🔄 Force refreshing virtual environment..."
        check_python
        setup_venv
        setup_secrets
        run_tests
        ;;
    --setup-only)
        echo "🔧 Setup only mode..."
        check_python
        if check_venv_freshness; then
            echo "✅ Virtual environment already good"
        else
            setup_venv
        fi
        setup_secrets
        echo "✅ Setup complete"
        ;;
    --test-only)
        echo "🧪 Test only mode..."
        if [ -d "venv" ]; then
            run_tests
        else
            echo "❌ No virtual environment found. Run without --test-only first."
            exit 1
        fi
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --force-refresh    Force refresh the virtual environment"
        echo "  --setup-only       Only setup environment, don't run tests"
        echo "  --test-only        Only run tests, assume environment is ready"
        echo "  --help, -h         Show this help message"
        echo ""
        echo "Default: Interactive setup and test"
        ;;
    "")
        main
        ;;
    *)
        echo "❌ Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac