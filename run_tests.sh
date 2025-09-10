#!/bin/bash

# Test runner script for Telegive Bot Service

set -e

echo "🧪 Running Telegive Bot Service Test Suite"
echo "=========================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run:"
    echo "   python -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Install test dependencies if not already installed
echo "📦 Installing test dependencies..."
pip install -q pytest pytest-cov pytest-mock pytest-flask

# Set test environment variables
export FLASK_ENV=testing
export DATABASE_URL=sqlite:///test.db
export REDIS_URL=redis://localhost:6379/15

# Create test database
echo "🗄️  Setting up test database..."
python -c "
from app import create_app
from models import db
app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///test.db'})
with app.app_context():
    db.create_all()
"

# Run different test suites based on argument
case "${1:-all}" in
    "unit")
        echo "🔬 Running unit tests..."
        pytest tests/test_models.py tests/test_handlers.py -v --tb=short
        ;;
    "integration")
        echo "🔗 Running integration tests..."
        pytest tests/test_integration.py -v --tb=short
        ;;
    "routes")
        echo "🛣️  Running route tests..."
        pytest tests/test_routes.py -v --tb=short
        ;;
    "coverage")
        echo "📊 Running tests with coverage..."
        pytest --cov=. --cov-report=term-missing --cov-report=html:htmlcov --cov-fail-under=80
        echo "📈 Coverage report generated in htmlcov/index.html"
        ;;
    "quick")
        echo "⚡ Running quick test suite..."
        pytest tests/test_models.py::TestBotInteraction::test_create_bot_interaction \
               tests/test_handlers.py::TestMessageHandler::test_handle_start_command \
               tests/test_routes.py::TestHealthRoutes::test_health_check_success \
               -v --tb=short
        ;;
    "all"|*)
        echo "🎯 Running all tests..."
        pytest -v --tb=short
        ;;
esac

# Check test results
if [ $? -eq 0 ]; then
    echo "✅ All tests passed!"
    
    # Clean up test database
    rm -f test.db
    
    echo ""
    echo "🎉 Test suite completed successfully!"
    echo ""
    echo "Available test commands:"
    echo "  ./run_tests.sh unit        - Run unit tests only"
    echo "  ./run_tests.sh integration - Run integration tests only"
    echo "  ./run_tests.sh routes      - Run route tests only"
    echo "  ./run_tests.sh coverage    - Run with coverage report"
    echo "  ./run_tests.sh quick       - Run quick test subset"
    echo "  ./run_tests.sh all         - Run all tests (default)"
else
    echo "❌ Some tests failed!"
    echo ""
    echo "💡 Tips for debugging:"
    echo "  - Check the test output above for specific failures"
    echo "  - Run individual test files: pytest tests/test_models.py -v"
    echo "  - Run specific test: pytest tests/test_models.py::TestBotInteraction::test_create_bot_interaction -v"
    echo "  - Add --pdb flag to drop into debugger on failure"
    
    # Clean up test database
    rm -f test.db
    
    exit 1
fi

