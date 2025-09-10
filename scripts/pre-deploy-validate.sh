#!/bin/bash
# scripts/pre-deploy-validate.sh
# Comprehensive pre-deployment validation for Telegive Bot Service

set -e  # Exit on any error

echo "🔍 Starting pre-deployment validation for Telegive Bot Service..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Validation counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

run_check() {
    local check_name="$1"
    local check_command="$2"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo ""
    print_info "Running check: $check_name"
    
    if eval "$check_command"; then
        print_status "$check_name passed"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        print_error "$check_name failed"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# 1. Validate Python environment
validate_python() {
    if ! command -v python3 &> /dev/null; then
        echo "Python3 is not installed"
        return 1
    fi
    
    # Check Python version
    python_version=$(python3 --version | cut -d' ' -f2)
    required_version="3.11"
    
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
        echo "Python version $python_version is too old. Required: $required_version+"
        return 1
    fi
    
    echo "Python $python_version is available and compatible"
    return 0
}

# 2. Validate requirements.txt
validate_requirements() {
    if [ ! -f "requirements.txt" ]; then
        echo "requirements.txt not found"
        return 1
    fi
    
    # Test requirements installation in temporary environment
    python3 -m venv temp_venv
    source temp_venv/bin/activate
    
    if ! pip install --quiet -r requirements.txt; then
        deactivate
        rm -rf temp_venv
        echo "Failed to install requirements"
        return 1
    fi
    
    deactivate
    rm -rf temp_venv
    echo "All requirements are valid and installable"
    return 0
}

# 3. Validate environment variables
validate_environment() {
    if [ ! -f ".env.example" ]; then
        echo ".env.example file not found"
        return 1
    fi
    
    # Check if all required variables are documented
    required_vars=(
        "DATABASE_URL"
        "SECRET_KEY" 
        "TELEGIVE_AUTH_URL"
        "TELEGIVE_CHANNEL_URL"
        "TELEGIVE_GIVEAWAY_URL"
        "TELEGIVE_PARTICIPANT_URL"
        "TELEGIVE_MEDIA_URL"
        "WEBHOOK_BASE_URL"
        "SERVICE_PORT"
    )
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" .env.example; then
            echo "Required variable $var not found in .env.example"
            return 1
        fi
    done
    
    echo "All required environment variables are documented"
    return 0
}

# 4. Validate deployment configuration
validate_deployment_config() {
    procfile_exists=false
    railway_json_exists=false
    dockerfile_exists=false
    
    if [ -f "Procfile" ]; then
        procfile_exists=true
    fi
    
    if [ -f "railway.json" ]; then
        railway_json_exists=true
    fi
    
    if [ -f "Dockerfile" ]; then
        dockerfile_exists=true
    fi
    
    # Check that at least one deployment method is configured
    if [ "$procfile_exists" = false ] && [ "$railway_json_exists" = false ] && [ "$dockerfile_exists" = false ]; then
        echo "No deployment configuration found. Need Procfile, railway.json, or Dockerfile"
        return 1
    fi
    
    # Validate railway.json if it exists
    if [ "$railway_json_exists" = true ]; then
        if ! python3 -c "import json; json.load(open('railway.json'))" 2>/dev/null; then
            echo "railway.json is not valid JSON"
            return 1
        fi
    fi
    
    echo "Deployment configuration is valid"
    return 0
}

# 5. Validate Flask application structure
validate_flask_app() {
    if [ ! -f "app.py" ]; then
        echo "app.py not found"
        return 1
    fi
    
    # Test if app can be imported
    if ! python3 -c "
import sys
sys.path.append('.')
try:
    from app import app
    print('Flask app imports successfully')
except Exception as e:
    print(f'Flask app import failed: {e}')
    sys.exit(1)
"; then
        echo "Flask application validation failed"
        return 1
    fi
    
    echo "Flask application structure is valid"
    return 0
}

# 6. Validate database models
validate_database_models() {
    if ! python3 -c "
import sys
sys.path.append('.')
import os
os.environ['DATABASE_URL'] = 'sqlite:///test_validation.db'
try:
    from app import create_app
    from models import db
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///test_validation.db'})
    with app.app_context():
        db.create_all()
    print('Database models are valid')
    import os
    if os.path.exists('test_validation.db'):
        os.remove('test_validation.db')
except Exception as e:
    print(f'Database model validation failed: {e}')
    sys.exit(1)
"; then
        echo "Database model validation failed"
        return 1
    fi
    
    echo "Database models are valid"
    return 0
}

# 7. Validate health endpoints
validate_health_endpoints() {
    if ! python3 -c "
import sys
sys.path.append('.')
import os
os.environ['DATABASE_URL'] = 'sqlite:///test_health.db'
try:
    from app import create_app
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///test_health.db'})
    client = app.test_client()
    
    # Test health endpoints
    endpoints = ['/health']
    for endpoint in endpoints:
        response = client.get(endpoint)
        if response.status_code not in [200, 503]:  # 503 is acceptable for unhealthy state
            raise Exception(f'Health endpoint {endpoint} returned {response.status_code}')
    
    print('Health endpoints are working')
    import os
    if os.path.exists('test_health.db'):
        os.remove('test_health.db')
except Exception as e:
    print(f'Health endpoint validation failed: {e}')
    sys.exit(1)
"; then
        echo "Health endpoint validation failed"
        return 1
    fi
    
    echo "Health endpoints are working"
    return 0
}

# 8. Validate API routes
validate_api_routes() {
    if ! python3 -c "
import sys
sys.path.append('.')
import os
os.environ['DATABASE_URL'] = 'sqlite:///test_routes.db'
try:
    from app import create_app
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///test_routes.db'})
    
    # Check if blueprints are registered
    blueprint_count = len(app.blueprints)
    if blueprint_count == 0:
        raise Exception('No blueprints registered')
    
    print(f'{blueprint_count} blueprints registered')
    import os
    if os.path.exists('test_routes.db'):
        os.remove('test_routes.db')
except Exception as e:
    print(f'API route validation failed: {e}')
    sys.exit(1)
"; then
        echo "API route validation failed"
        return 1
    fi
    
    echo "API routes are valid"
    return 0
}

# 9. Validate project structure
validate_project_structure() {
    required_dirs=("models" "routes" "handlers" "services" "utils" "tests")
    required_files=("app.py" "requirements.txt" ".gitignore" "README.md")
    
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            echo "Required directory $dir not found"
            return 1
        fi
    done
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            echo "Required file $file not found"
            return 1
        fi
    done
    
    echo "Project structure is valid"
    return 0
}

# 10. Validate tests
validate_tests() {
    if [ ! -d "tests" ]; then
        echo "Tests directory not found"
        return 1
    fi
    
    # Check if test files exist
    test_files=$(find tests -name "test_*.py" | wc -l)
    if [ "$test_files" -eq 0 ]; then
        echo "No test files found in tests directory"
        return 1
    fi
    
    # Try to run tests
    if ! python3 -m pytest tests/ --tb=short -q; then
        echo "Some tests are failing"
        return 1
    fi
    
    echo "All tests are passing"
    return 0
}

# 11. Validate security configuration
validate_security() {
    # Check for hardcoded secrets
    if grep -r "secret.*=" . --include="*.py" | grep -v ".env" | grep -v "example" | grep -i "password\|key\|token" | grep -v "SECRET_KEY.*os.getenv"; then
        echo "Potential hardcoded secrets found"
        return 1
    fi
    
    # Check CORS configuration
    if ! grep -r "CORS" . --include="*.py" >/dev/null; then
        echo "CORS configuration not found"
        return 1
    fi
    
    echo "Security configuration is valid"
    return 0
}

# 12. Validate documentation
validate_documentation() {
    if [ ! -f "README.md" ]; then
        echo "README.md not found"
        return 1
    fi
    
    # Check if README has essential sections
    essential_sections=("Installation" "Configuration" "API" "Deployment")
    for section in "${essential_sections[@]}"; do
        if ! grep -i "$section" README.md >/dev/null; then
            echo "README.md missing section: $section"
            return 1
        fi
    done
    
    echo "Documentation is adequate"
    return 0
}

# Run all validations
echo "🚀 Starting comprehensive validation..."
echo "======================================"

run_check "Python Environment" "validate_python"
run_check "Requirements" "validate_requirements"
run_check "Environment Variables" "validate_environment"
run_check "Deployment Configuration" "validate_deployment_config"
run_check "Flask Application" "validate_flask_app"
run_check "Database Models" "validate_database_models"
run_check "Health Endpoints" "validate_health_endpoints"
run_check "API Routes" "validate_api_routes"
run_check "Project Structure" "validate_project_structure"
run_check "Tests" "validate_tests"
run_check "Security Configuration" "validate_security"
run_check "Documentation" "validate_documentation"

# Summary
echo ""
echo "🎉 Pre-deployment validation completed!"
echo "======================================"
echo "📊 Summary:"
echo "   Total checks: $TOTAL_CHECKS"
echo "   Passed: $PASSED_CHECKS"
echo "   Failed: $FAILED_CHECKS"

if [ $FAILED_CHECKS -eq 0 ]; then
    echo ""
    print_status "All validations passed! Ready for deployment 🚀"
    echo ""
    echo "📋 Validation Results:"
    echo "   - Python environment: ✅"
    echo "   - Requirements: ✅"
    echo "   - Environment variables: ✅"
    echo "   - Deployment config: ✅"
    echo "   - Flask application: ✅"
    echo "   - Database models: ✅"
    echo "   - Health endpoints: ✅"
    echo "   - API routes: ✅"
    echo "   - Project structure: ✅"
    echo "   - Tests: ✅"
    echo "   - Security: ✅"
    echo "   - Documentation: ✅"
    echo ""
    echo "🚀 Ready for deployment!"
    exit 0
else
    echo ""
    print_error "Some validations failed! Please fix the issues before deployment."
    exit 1
fi

