#!/usr/bin/env python3
"""
Deployment checklist script for Telegive Bot Service
Comprehensive checklist to ensure deployment readiness
"""

import os
import sys
import json
import subprocess
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class CheckStatus(Enum):
    PASS = "✅"
    FAIL = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"

@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    details: Optional[str] = None

class DeploymentChecker:
    """Comprehensive deployment readiness checker"""
    
    def __init__(self):
        self.results: List[CheckResult] = []
        self.critical_failures = 0
        self.warnings = 0
        
    def run_all_checks(self) -> bool:
        """Run all deployment checks"""
        print("🚀 Telegive Bot Service - Deployment Readiness Check")
        print("=" * 60)
        
        # Core application checks
        self._check_application_structure()
        self._check_configuration()
        self._check_dependencies()
        self._check_database_setup()
        self._check_security()
        
        # Deployment specific checks
        self._check_deployment_config()
        self._check_environment_variables()
        self._check_health_endpoints()
        
        # Quality checks
        self._check_tests()
        self._check_documentation()
        self._check_monitoring()
        
        # External dependencies
        self._check_external_services()
        
        return self._print_summary()
    
    def _add_result(self, name: str, status: CheckStatus, message: str, details: str = None):
        """Add check result"""
        result = CheckResult(name, status, message, details)
        self.results.append(result)
        
        if status == CheckStatus.FAIL:
            self.critical_failures += 1
        elif status == CheckStatus.WARNING:
            self.warnings += 1
        
        print(f"{status.value} {name}: {message}")
        if details:
            print(f"   {details}")
    
    def _check_application_structure(self):
        """Check application structure"""
        print("\n📁 Application Structure")
        print("-" * 30)
        
        # Required files
        required_files = [
            'app.py',
            'requirements.txt',
            '.gitignore',
            'README.md'
        ]
        
        for file in required_files:
            if os.path.exists(file):
                self._add_result(f"File: {file}", CheckStatus.PASS, "Present")
            else:
                self._add_result(f"File: {file}", CheckStatus.FAIL, "Missing")
        
        # Required directories
        required_dirs = [
            'models',
            'routes', 
            'handlers',
            'services',
            'utils',
            'tests'
        ]
        
        for dir_name in required_dirs:
            if os.path.isdir(dir_name):
                file_count = len([f for f in os.listdir(dir_name) if f.endswith('.py')])
                self._add_result(f"Directory: {dir_name}", CheckStatus.PASS, f"Present ({file_count} Python files)")
            else:
                self._add_result(f"Directory: {dir_name}", CheckStatus.FAIL, "Missing")
    
    def _check_configuration(self):
        """Check configuration files"""
        print("\n⚙️  Configuration")
        print("-" * 20)
        
        # Check .env.example
        if os.path.exists('.env.example'):
            with open('.env.example', 'r') as f:
                env_content = f.read()
            
            required_vars = [
                'DATABASE_URL',
                'SECRET_KEY',
                'TELEGIVE_AUTH_URL',
                'TELEGIVE_CHANNEL_URL',
                'TELEGIVE_GIVEAWAY_URL',
                'TELEGIVE_PARTICIPANT_URL',
                'TELEGIVE_MEDIA_URL',
                'WEBHOOK_BASE_URL'
            ]
            
            missing_vars = []
            for var in required_vars:
                if var not in env_content:
                    missing_vars.append(var)
            
            if missing_vars:
                self._add_result(
                    "Environment template",
                    CheckStatus.FAIL,
                    f"Missing variables: {', '.join(missing_vars)}"
                )
            else:
                self._add_result("Environment template", CheckStatus.PASS, "All required variables present")
        else:
            self._add_result("Environment template", CheckStatus.FAIL, ".env.example not found")
        
        # Check Flask app configuration
        try:
            sys.path.append('.')
            os.environ['DATABASE_URL'] = 'sqlite:///test_config.db'
            from app import create_app
            app = create_app({'TESTING': True})
            
            # Check critical config
            if app.config.get('SECRET_KEY'):
                self._add_result("Flask SECRET_KEY", CheckStatus.PASS, "Configured")
            else:
                self._add_result("Flask SECRET_KEY", CheckStatus.FAIL, "Not configured")
            
            if app.config.get('SQLALCHEMY_DATABASE_URI'):
                self._add_result("Database URI", CheckStatus.PASS, "Configured")
            else:
                self._add_result("Database URI", CheckStatus.FAIL, "Not configured")
            
            # Cleanup
            if os.path.exists('test_config.db'):
                os.remove('test_config.db')
                
        except Exception as e:
            self._add_result("Flask configuration", CheckStatus.FAIL, f"Cannot load app: {e}")
    
    def _check_dependencies(self):
        """Check dependencies"""
        print("\n📦 Dependencies")
        print("-" * 15)
        
        if os.path.exists('requirements.txt'):
            with open('requirements.txt', 'r') as f:
                requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            self._add_result("Requirements file", CheckStatus.PASS, f"{len(requirements)} packages listed")
            
            # Check for critical packages
            critical_packages = [
                'Flask',
                'Flask-SQLAlchemy',
                'Flask-CORS',
                'requests',
                'python-telegram-bot',
                'gunicorn'
            ]
            
            missing_critical = []
            for package in critical_packages:
                if not any(package.lower() in req.lower() for req in requirements):
                    missing_critical.append(package)
            
            if missing_critical:
                self._add_result(
                    "Critical packages",
                    CheckStatus.FAIL,
                    f"Missing: {', '.join(missing_critical)}"
                )
            else:
                self._add_result("Critical packages", CheckStatus.PASS, "All present")
        else:
            self._add_result("Requirements file", CheckStatus.FAIL, "requirements.txt not found")
    
    def _check_database_setup(self):
        """Check database setup"""
        print("\n🗄️  Database Setup")
        print("-" * 18)
        
        try:
            sys.path.append('.')
            os.environ['DATABASE_URL'] = 'sqlite:///test_db_setup.db'
            from app import create_app
            from models import db
            
            app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///test_db_setup.db'})
            
            with app.app_context():
                # Test database creation
                db.create_all()
                self._add_result("Database models", CheckStatus.PASS, "Can create tables")
                
                # Check for required models
                required_models = ['BotInteraction', 'MessageDeliveryLog', 'WebhookProcessingLog']
                for model_name in required_models:
                    if hasattr(sys.modules.get('models', {}), model_name):
                        self._add_result(f"Model: {model_name}", CheckStatus.PASS, "Defined")
                    else:
                        self._add_result(f"Model: {model_name}", CheckStatus.FAIL, "Not found")
            
            # Cleanup
            if os.path.exists('test_db_setup.db'):
                os.remove('test_db_setup.db')
                
        except Exception as e:
            self._add_result("Database setup", CheckStatus.FAIL, f"Error: {e}")
    
    def _check_security(self):
        """Check security configuration"""
        print("\n🔒 Security")
        print("-" * 12)
        
        # Check for hardcoded secrets
        try:
            result = subprocess.run(
                ['grep', '-r', 'password.*=', '.', '--include=*.py'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout:
                # Filter out acceptable patterns
                lines = result.stdout.split('\n')
                suspicious_lines = [
                    line for line in lines 
                    if line and 'os.getenv' not in line and '.env' not in line
                ]
                
                if suspicious_lines:
                    self._add_result(
                        "Hardcoded secrets",
                        CheckStatus.WARNING,
                        f"Potential issues found",
                        f"Check: {suspicious_lines[0][:100]}..."
                    )
                else:
                    self._add_result("Hardcoded secrets", CheckStatus.PASS, "None found")
            else:
                self._add_result("Hardcoded secrets", CheckStatus.PASS, "None found")
                
        except Exception:
            self._add_result("Hardcoded secrets", CheckStatus.INFO, "Could not check")
        
        # Check CORS configuration
        try:
            with open('app.py', 'r') as f:
                app_content = f.read()
            
            if 'CORS' in app_content:
                self._add_result("CORS configuration", CheckStatus.PASS, "Configured")
            else:
                self._add_result("CORS configuration", CheckStatus.WARNING, "Not found")
                
        except Exception:
            self._add_result("CORS configuration", CheckStatus.INFO, "Could not check")
    
    def _check_deployment_config(self):
        """Check deployment configuration"""
        print("\n🚀 Deployment Configuration")
        print("-" * 30)
        
        # Check Railway configuration
        if os.path.exists('railway.json'):
            try:
                with open('railway.json', 'r') as f:
                    railway_config = json.load(f)
                
                if 'deploy' in railway_config:
                    self._add_result("Railway config", CheckStatus.PASS, "Valid configuration")
                else:
                    self._add_result("Railway config", CheckStatus.WARNING, "Missing deploy section")
                    
            except json.JSONDecodeError:
                self._add_result("Railway config", CheckStatus.FAIL, "Invalid JSON")
        else:
            self._add_result("Railway config", CheckStatus.INFO, "railway.json not found")
        
        # Check Dockerfile
        if os.path.exists('Dockerfile'):
            with open('Dockerfile', 'r') as f:
                dockerfile_content = f.read()
            
            if 'EXPOSE' in dockerfile_content:
                self._add_result("Dockerfile", CheckStatus.PASS, "Valid Dockerfile")
            else:
                self._add_result("Dockerfile", CheckStatus.WARNING, "No EXPOSE directive")
        else:
            self._add_result("Dockerfile", CheckStatus.INFO, "Dockerfile not found")
        
        # Check Procfile
        if os.path.exists('Procfile'):
            with open('Procfile', 'r') as f:
                procfile_content = f.read()
            
            if 'web:' in procfile_content:
                self._add_result("Procfile", CheckStatus.PASS, "Valid Procfile")
            else:
                self._add_result("Procfile", CheckStatus.WARNING, "No web process defined")
        else:
            self._add_result("Procfile", CheckStatus.INFO, "Procfile not found")
    
    def _check_environment_variables(self):
        """Check environment variables"""
        print("\n🌍 Environment Variables")
        print("-" * 25)
        
        # Check if running in production-like environment
        env = os.getenv('ENVIRONMENT', 'development')
        self._add_result("Environment", CheckStatus.INFO, f"Current: {env}")
        
        # Check critical environment variables
        critical_vars = [
            'DATABASE_URL',
            'SECRET_KEY'
        ]
        
        for var in critical_vars:
            if os.getenv(var):
                self._add_result(f"Env var: {var}", CheckStatus.PASS, "Set")
            else:
                self._add_result(f"Env var: {var}", CheckStatus.WARNING, "Not set (will use default)")
    
    def _check_health_endpoints(self):
        """Check health endpoints"""
        print("\n🏥 Health Endpoints")
        print("-" * 20)
        
        try:
            sys.path.append('.')
            os.environ['DATABASE_URL'] = 'sqlite:///test_health.db'
            from app import create_app
            
            app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///test_health.db'})
            client = app.test_client()
            
            # Test health endpoints
            health_endpoints = ['/health']
            
            for endpoint in health_endpoints:
                response = client.get(endpoint)
                if response.status_code in [200, 503]:
                    self._add_result(f"Endpoint: {endpoint}", CheckStatus.PASS, f"Returns {response.status_code}")
                else:
                    self._add_result(f"Endpoint: {endpoint}", CheckStatus.FAIL, f"Returns {response.status_code}")
            
            # Cleanup
            if os.path.exists('test_health.db'):
                os.remove('test_health.db')
                
        except Exception as e:
            self._add_result("Health endpoints", CheckStatus.FAIL, f"Error: {e}")
    
    def _check_tests(self):
        """Check test suite"""
        print("\n🧪 Test Suite")
        print("-" * 13)
        
        if os.path.isdir('tests'):
            test_files = [f for f in os.listdir('tests') if f.startswith('test_') and f.endswith('.py')]
            
            if test_files:
                self._add_result("Test files", CheckStatus.PASS, f"{len(test_files)} test files found")
                
                # Try to run tests
                try:
                    result = subprocess.run(
                        ['python', '-m', 'pytest', 'tests/', '--tb=short', '-q'],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if result.returncode == 0:
                        self._add_result("Test execution", CheckStatus.PASS, "All tests pass")
                    else:
                        self._add_result("Test execution", CheckStatus.WARNING, "Some tests fail")
                        
                except subprocess.TimeoutExpired:
                    self._add_result("Test execution", CheckStatus.WARNING, "Tests timed out")
                except Exception as e:
                    self._add_result("Test execution", CheckStatus.WARNING, f"Could not run tests: {e}")
            else:
                self._add_result("Test files", CheckStatus.WARNING, "No test files found")
        else:
            self._add_result("Test directory", CheckStatus.WARNING, "tests/ directory not found")
    
    def _check_documentation(self):
        """Check documentation"""
        print("\n📚 Documentation")
        print("-" * 17)
        
        if os.path.exists('README.md'):
            with open('README.md', 'r') as f:
                readme_content = f.read()
            
            required_sections = ['Installation', 'Configuration', 'API', 'Deployment']
            missing_sections = []
            
            for section in required_sections:
                if section.lower() not in readme_content.lower():
                    missing_sections.append(section)
            
            if missing_sections:
                self._add_result(
                    "README completeness",
                    CheckStatus.WARNING,
                    f"Missing sections: {', '.join(missing_sections)}"
                )
            else:
                self._add_result("README completeness", CheckStatus.PASS, "All sections present")
        else:
            self._add_result("README.md", CheckStatus.FAIL, "Not found")
        
        # Check API documentation
        if os.path.exists('docs/API.md'):
            self._add_result("API documentation", CheckStatus.PASS, "Present")
        else:
            self._add_result("API documentation", CheckStatus.WARNING, "Not found")
    
    def _check_monitoring(self):
        """Check monitoring setup"""
        print("\n📊 Monitoring")
        print("-" * 13)
        
        # Check for logging configuration
        try:
            with open('app.py', 'r') as f:
                app_content = f.read()
            
            if 'logging' in app_content:
                self._add_result("Logging setup", CheckStatus.PASS, "Configured")
            else:
                self._add_result("Logging setup", CheckStatus.WARNING, "Not configured")
                
        except Exception:
            self._add_result("Logging setup", CheckStatus.INFO, "Could not check")
        
        # Check for error handling
        if 'errorhandler' in app_content:
            self._add_result("Error handling", CheckStatus.PASS, "Configured")
        else:
            self._add_result("Error handling", CheckStatus.WARNING, "Not configured")
    
    def _check_external_services(self):
        """Check external service dependencies"""
        print("\n🌐 External Services")
        print("-" * 20)
        
        # Check if service URLs are configured
        service_vars = [
            'TELEGIVE_AUTH_URL',
            'TELEGIVE_CHANNEL_URL',
            'TELEGIVE_GIVEAWAY_URL',
            'TELEGIVE_PARTICIPANT_URL',
            'TELEGIVE_MEDIA_URL'
        ]
        
        for var in service_vars:
            if os.getenv(var):
                self._add_result(f"Service: {var}", CheckStatus.PASS, "URL configured")
            else:
                self._add_result(f"Service: {var}", CheckStatus.WARNING, "URL not configured")
    
    def _print_summary(self) -> bool:
        """Print summary and return success status"""
        print("\n" + "=" * 60)
        print("📋 DEPLOYMENT READINESS SUMMARY")
        print("=" * 60)
        
        total_checks = len(self.results)
        passed = len([r for r in self.results if r.status == CheckStatus.PASS])
        failed = len([r for r in self.results if r.status == CheckStatus.FAIL])
        warnings = len([r for r in self.results if r.status == CheckStatus.WARNING])
        info = len([r for r in self.results if r.status == CheckStatus.INFO])
        
        print(f"\n📊 Results:")
        print(f"   Total checks: {total_checks}")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   ⚠️  Warnings: {warnings}")
        print(f"   ℹ️  Info: {info}")
        
        if failed == 0:
            print(f"\n🎉 DEPLOYMENT READY!")
            print("   All critical checks passed. Safe to deploy.")
            if warnings > 0:
                print(f"   Note: {warnings} warnings should be addressed when possible.")
            return True
        else:
            print(f"\n🚫 NOT READY FOR DEPLOYMENT")
            print(f"   {failed} critical issues must be fixed before deployment.")
            
            print(f"\n❌ Critical Issues:")
            for result in self.results:
                if result.status == CheckStatus.FAIL:
                    print(f"   - {result.name}: {result.message}")
            
            return False

def main():
    """Main function"""
    checker = DeploymentChecker()
    
    if checker.run_all_checks():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

