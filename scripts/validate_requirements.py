#!/usr/bin/env python3
"""
Requirements validation script for Telegive Bot Service
Validates all packages in requirements.txt for existence, compatibility, and security
"""

import subprocess
import sys
import pkg_resources
from packaging import version
import requests
import json
import time
from typing import List, Dict, Tuple, Optional

class RequirementsValidator:
    """Comprehensive requirements.txt validator"""
    
    def __init__(self, requirements_file: str = 'requirements.txt'):
        self.requirements_file = requirements_file
        self.invalid_packages = []
        self.outdated_packages = []
        self.security_issues = []
        self.compatibility_issues = []
        
    def validate_requirements(self) -> bool:
        """Main validation function"""
        print("🔍 Validating requirements.txt...")
        print("=" * 50)
        
        if not self._load_requirements():
            return False
        
        success = True
        success &= self._validate_package_existence()
        success &= self._validate_versions()
        success &= self._check_security_vulnerabilities()
        success &= self._check_compatibility()
        success &= self._test_installation()
        
        self._print_summary()
        return success
    
    def _load_requirements(self) -> bool:
        """Load and parse requirements.txt"""
        try:
            with open(self.requirements_file, 'r') as f:
                content = f.read().strip()
            
            self.requirements = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    self.requirements.append(line)
            
            print(f"📦 Found {len(self.requirements)} packages to validate")
            return True
            
        except FileNotFoundError:
            print(f"❌ {self.requirements_file} not found")
            return False
        except Exception as e:
            print(f"❌ Error reading {self.requirements_file}: {e}")
            return False
    
    def _parse_requirement(self, req: str) -> Tuple[str, Optional[str], str]:
        """Parse requirement string into name, version, and operator"""
        operators = ['==', '>=', '<=', '>', '<', '~=', '!=']
        
        for op in operators:
            if op in req:
                parts = req.split(op)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip(), op
        
        return req.strip(), None, None
    
    def _validate_package_existence(self) -> bool:
        """Check if all packages exist on PyPI"""
        print("\n🌐 Checking package existence on PyPI...")
        
        all_valid = True
        for req in self.requirements:
            package_name, _, _ = self._parse_requirement(req)
            
            try:
                response = requests.get(
                    f'https://pypi.org/pypi/{package_name}/json',
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"  ✅ {package_name}")
                else:
                    print(f"  ❌ {package_name} - Not found on PyPI")
                    self.invalid_packages.append(package_name)
                    all_valid = False
                    
            except Exception as e:
                print(f"  ⚠️  {package_name} - Could not verify: {e}")
                time.sleep(0.1)  # Rate limiting
        
        return all_valid
    
    def _validate_versions(self) -> bool:
        """Validate package versions and check for updates"""
        print("\n📊 Checking package versions...")
        
        all_valid = True
        for req in self.requirements:
            package_name, package_version, operator = self._parse_requirement(req)
            
            if not package_version:
                print(f"  ⚠️  {package_name} - No version specified")
                continue
            
            try:
                response = requests.get(
                    f'https://pypi.org/pypi/{package_name}/json',
                    timeout=10
                )
                
                if response.status_code != 200:
                    continue
                
                package_info = response.json()
                latest_version = package_info['info']['version']
                available_versions = list(package_info['releases'].keys())
                
                # Check if specified version exists
                if package_version not in available_versions:
                    print(f"  ❌ {package_name}=={package_version} - Version not found")
                    self.invalid_packages.append(f"{package_name}=={package_version}")
                    all_valid = False
                    continue
                
                # Check if version is outdated (only for == operator)
                if operator == '==' and version.parse(package_version) < version.parse(latest_version):
                    print(f"  📈 {package_name}: {package_version} -> {latest_version} (outdated)")
                    self.outdated_packages.append(f"{package_name}: {package_version} -> {latest_version}")
                else:
                    print(f"  ✅ {package_name}=={package_version}")
                
            except Exception as e:
                print(f"  ⚠️  {package_name} - Could not check version: {e}")
                time.sleep(0.1)  # Rate limiting
        
        return all_valid
    
    def _check_security_vulnerabilities(self) -> bool:
        """Check for known security vulnerabilities using safety"""
        print("\n🔒 Checking for security vulnerabilities...")
        
        try:
            # Try to use safety if available
            result = subprocess.run(
                ['safety', 'check', '--json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print("  ✅ No known security vulnerabilities found")
                return True
            else:
                try:
                    vulnerabilities = json.loads(result.stdout)
                    for vuln in vulnerabilities:
                        package = vuln.get('package', 'Unknown')
                        version = vuln.get('installed_version', 'Unknown')
                        advisory = vuln.get('advisory', 'No details')
                        print(f"  🚨 {package} {version}: {advisory}")
                        self.security_issues.append(f"{package} {version}: {advisory}")
                    return False
                except json.JSONDecodeError:
                    print("  ⚠️  Could not parse safety output")
                    return True
                    
        except FileNotFoundError:
            print("  ⚠️  Safety not installed - skipping security check")
            print("     Install with: pip install safety")
            return True
        except Exception as e:
            print(f"  ⚠️  Security check failed: {e}")
            return True
    
    def _check_compatibility(self) -> bool:
        """Check Python version compatibility"""
        print("\n🐍 Checking Python compatibility...")
        
        python_version = sys.version_info
        print(f"  Current Python: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # Check if packages support current Python version
        compatible = True
        for req in self.requirements:
            package_name, _, _ = self._parse_requirement(req)
            
            try:
                response = requests.get(
                    f'https://pypi.org/pypi/{package_name}/json',
                    timeout=10
                )
                
                if response.status_code != 200:
                    continue
                
                package_info = response.json()
                classifiers = package_info['info'].get('classifiers', [])
                
                # Look for Python version classifiers
                python_versions = [
                    c for c in classifiers 
                    if c.startswith('Programming Language :: Python ::')
                ]
                
                if python_versions:
                    current_version_supported = any(
                        f"{python_version.major}.{python_version.minor}" in pv
                        for pv in python_versions
                    )
                    
                    if not current_version_supported:
                        print(f"  ⚠️  {package_name} - May not support Python {python_version.major}.{python_version.minor}")
                        self.compatibility_issues.append(f"{package_name} - Python {python_version.major}.{python_version.minor}")
                        compatible = False
                    else:
                        print(f"  ✅ {package_name}")
                else:
                    print(f"  ❓ {package_name} - No Python version info")
                
            except Exception as e:
                print(f"  ⚠️  {package_name} - Could not check compatibility: {e}")
                time.sleep(0.1)  # Rate limiting
        
        return compatible
    
    def _test_installation(self) -> bool:
        """Test actual installation in a temporary environment"""
        print("\n🧪 Testing installation in temporary environment...")
        
        try:
            # Create temporary virtual environment
            subprocess.run(['python3', '-m', 'venv', 'temp_validation_env'], check=True)
            
            # Install requirements
            result = subprocess.run([
                'temp_validation_env/bin/pip', 'install', '-r', self.requirements_file
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print("  ✅ All packages installed successfully")
                success = True
            else:
                print("  ❌ Installation failed:")
                print(f"     {result.stderr}")
                success = False
            
            # Cleanup
            subprocess.run(['rm', '-rf', 'temp_validation_env'])
            return success
            
        except subprocess.TimeoutExpired:
            print("  ❌ Installation timed out")
            subprocess.run(['rm', '-rf', 'temp_validation_env'])
            return False
        except Exception as e:
            print(f"  ❌ Installation test failed: {e}")
            subprocess.run(['rm', '-rf', 'temp_validation_env'])
            return False
    
    def _print_summary(self):
        """Print validation summary"""
        print("\n" + "=" * 50)
        print("📋 VALIDATION SUMMARY")
        print("=" * 50)
        
        if self.invalid_packages:
            print(f"\n❌ Invalid packages ({len(self.invalid_packages)}):")
            for pkg in self.invalid_packages:
                print(f"   - {pkg}")
        
        if self.outdated_packages:
            print(f"\n📈 Outdated packages ({len(self.outdated_packages)}):")
            for pkg in self.outdated_packages:
                print(f"   - {pkg}")
        
        if self.security_issues:
            print(f"\n🚨 Security issues ({len(self.security_issues)}):")
            for issue in self.security_issues:
                print(f"   - {issue}")
        
        if self.compatibility_issues:
            print(f"\n⚠️  Compatibility issues ({len(self.compatibility_issues)}):")
            for issue in self.compatibility_issues:
                print(f"   - {issue}")
        
        if not any([self.invalid_packages, self.security_issues]):
            print("\n✅ All requirements are valid and secure!")
        
        if self.outdated_packages:
            print(f"\n💡 Consider updating {len(self.outdated_packages)} outdated packages")
        
        print("\n🎯 Recommendations:")
        print("   - Pin all package versions with ==")
        print("   - Regularly update packages for security")
        print("   - Use virtual environments")
        print("   - Run 'pip install safety' for security scanning")

def main():
    """Main function"""
    validator = RequirementsValidator()
    
    if not validator.validate_requirements():
        print("\n❌ Requirements validation failed!")
        sys.exit(1)
    else:
        print("\n✅ Requirements validation passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()

