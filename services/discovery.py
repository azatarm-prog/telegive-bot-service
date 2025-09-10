"""
Service discovery with health monitoring for Telegive Bot Service
Provides automatic service discovery, health monitoring, and failover capabilities
"""

import requests
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import time
import json
from enum import Enum
from config.environment import env_manager

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    NOT_CONFIGURED = "not_configured"

@dataclass
class ServiceHealth:
    name: str
    url: str
    status: ServiceStatus
    last_check: datetime
    response_time: Optional[float] = None
    error: Optional[str] = None
    consecutive_failures: int = 0
    last_success: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

class ServiceDiscovery:
    """Service discovery with health monitoring and circuit breaker pattern"""
    
    def __init__(self):
        self.services: Dict[str, ServiceHealth] = {}
        self.check_interval = 30  # seconds
        self.timeout = 10
        self.max_consecutive_failures = 3
        self._running = False
        self._thread = None
        self._callbacks: Dict[str, List[Callable]] = {}
        
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize service registry from environment configuration"""
        service_configs = env_manager.get('SERVICES', {})
        
        for name, config in service_configs.items():
            if config.url:
                self.services[name] = ServiceHealth(
                    name=name,
                    url=config.url,
                    status=ServiceStatus.UNKNOWN,
                    last_check=datetime.utcnow(),
                    metadata={
                        'required': config.required,
                        'timeout': config.timeout,
                        'health_endpoint': config.health_endpoint
                    }
                )
                logger.info(f"Registered service: {name} at {config.url}")
            else:
                self.services[name] = ServiceHealth(
                    name=name,
                    url="",
                    status=ServiceStatus.NOT_CONFIGURED,
                    last_check=datetime.utcnow(),
                    metadata={
                        'required': config.required,
                        'timeout': config.timeout
                    }
                )
                logger.warning(f"Service {name} not configured (URL missing)")
    
    def start_monitoring(self):
        """Start background health monitoring"""
        if self._running:
            logger.warning("Service monitoring already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Service discovery monitoring started")
        
        # Perform initial health check
        self.check_all_services()
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Service discovery monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                self.check_all_services()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)  # Short delay before retrying
    
    def check_service_health(self, service_name: str) -> bool:
        """Check health of a specific service"""
        if service_name not in self.services:
            logger.warning(f"Service {service_name} not registered")
            return False
        
        service = self.services[service_name]
        
        if service.status == ServiceStatus.NOT_CONFIGURED:
            return False
        
        start_time = time.time()
        previous_status = service.status
        
        try:
            timeout = service.metadata.get('timeout', self.timeout)
            health_endpoint = service.metadata.get('health_endpoint', '/health')
            health_url = f"{service.url.rstrip('/')}{health_endpoint}"
            
            response = requests.get(health_url, timeout=timeout)
            response_time = time.time() - start_time
            
            # Consider service healthy if it returns 200 or 503 (degraded but functional)
            healthy = response.status_code in [200, 503]
            
            service.status = ServiceStatus.HEALTHY if healthy else ServiceStatus.UNHEALTHY
            service.response_time = response_time
            service.last_check = datetime.utcnow()
            service.error = None
            
            if healthy:
                service.consecutive_failures = 0
                service.last_success = datetime.utcnow()
                
                # Try to extract additional metadata from response
                try:
                    health_data = response.json()
                    service.metadata.update({
                        'version': health_data.get('version'),
                        'service_name': health_data.get('service'),
                        'last_health_data': health_data
                    })
                except:
                    pass  # Ignore JSON parsing errors
            else:
                service.consecutive_failures += 1
                service.error = f"HTTP {response.status_code}"
            
            # Trigger callbacks if status changed
            if previous_status != service.status:
                self._trigger_callbacks(service_name, service.status, previous_status)
            
            return healthy
            
        except requests.exceptions.Timeout:
            service.status = ServiceStatus.TIMEOUT
            service.response_time = time.time() - start_time
            service.last_check = datetime.utcnow()
            service.error = "Request timed out"
            service.consecutive_failures += 1
            
        except Exception as e:
            service.status = ServiceStatus.UNHEALTHY
            service.response_time = time.time() - start_time
            service.last_check = datetime.utcnow()
            service.error = str(e)
            service.consecutive_failures += 1
        
        # Trigger callbacks if status changed
        if previous_status != service.status:
            self._trigger_callbacks(service_name, service.status, previous_status)
        
        logger.warning(f"Health check failed for {service_name}: {service.error}")
        return False
    
    def check_all_services(self):
        """Check health of all services"""
        for service_name in self.services:
            if self.services[service_name].status != ServiceStatus.NOT_CONFIGURED:
                self.check_service_health(service_name)
    
    def get_service_health(self, service_name: str) -> Optional[ServiceHealth]:
        """Get health information for a specific service"""
        return self.services.get(service_name)
    
    def get_all_service_health(self) -> Dict[str, ServiceHealth]:
        """Get health information for all services"""
        return self.services.copy()
    
    def get_healthy_services(self) -> List[str]:
        """Get list of healthy service names"""
        return [
            name for name, health in self.services.items()
            if health.status == ServiceStatus.HEALTHY
        ]
    
    def get_unhealthy_services(self) -> List[str]:
        """Get list of unhealthy service names"""
        return [
            name for name, health in self.services.items()
            if health.status in [ServiceStatus.UNHEALTHY, ServiceStatus.TIMEOUT]
        ]
    
    def get_required_unhealthy_services(self) -> List[str]:
        """Get list of required services that are unhealthy"""
        return [
            name for name, health in self.services.items()
            if (health.status in [ServiceStatus.UNHEALTHY, ServiceStatus.TIMEOUT] and
                health.metadata.get('required', False))
        ]
    
    def is_service_healthy(self, service_name: str) -> bool:
        """Check if a service is currently healthy"""
        health = self.services.get(service_name)
        if not health:
            return False
        
        # Check if status is recent (within 2x check interval)
        age = datetime.utcnow() - health.last_check
        if age > timedelta(seconds=self.check_interval * 2):
            # Status is stale, check now
            return self.check_service_health(service_name)
        
        return health.status == ServiceStatus.HEALTHY
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if service is available (healthy or degraded)"""
        health = self.services.get(service_name)
        if not health:
            return False
        
        return health.status in [ServiceStatus.HEALTHY]
    
    def get_service_url(self, service_name: str) -> Optional[str]:
        """Get URL for a service if it's healthy"""
        health = self.services.get(service_name)
        if not health or not self.is_service_available(service_name):
            return None
        
        return health.url
    
    def get_service_url_force(self, service_name: str) -> Optional[str]:
        """Get URL for a service regardless of health status"""
        health = self.services.get(service_name)
        return health.url if health else None
    
    def is_circuit_open(self, service_name: str) -> bool:
        """Check if circuit breaker is open for a service"""
        health = self.services.get(service_name)
        if not health:
            return True
        
        return health.consecutive_failures >= self.max_consecutive_failures
    
    def register_callback(self, service_name: str, callback: Callable[[str, ServiceStatus, ServiceStatus], None]):
        """Register callback for service status changes"""
        if service_name not in self._callbacks:
            self._callbacks[service_name] = []
        
        self._callbacks[service_name].append(callback)
        logger.info(f"Registered callback for service {service_name}")
    
    def _trigger_callbacks(self, service_name: str, new_status: ServiceStatus, old_status: ServiceStatus):
        """Trigger callbacks for service status change"""
        callbacks = self._callbacks.get(service_name, [])
        
        for callback in callbacks:
            try:
                callback(service_name, new_status, old_status)
            except Exception as e:
                logger.error(f"Error in callback for {service_name}: {e}")
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """Get service discovery statistics"""
        total_services = len(self.services)
        healthy_count = len(self.get_healthy_services())
        unhealthy_count = len(self.get_unhealthy_services())
        not_configured_count = len([
            s for s in self.services.values()
            if s.status == ServiceStatus.NOT_CONFIGURED
        ])
        
        required_services = [
            name for name, health in self.services.items()
            if health.metadata.get('required', False)
        ]
        required_healthy = [
            name for name in required_services
            if self.is_service_healthy(name)
        ]
        
        return {
            'total_services': total_services,
            'healthy_services': healthy_count,
            'unhealthy_services': unhealthy_count,
            'not_configured_services': not_configured_count,
            'required_services_total': len(required_services),
            'required_services_healthy': len(required_healthy),
            'overall_health': 'healthy' if len(required_healthy) == len(required_services) else 'degraded',
            'last_check': max([s.last_check for s in self.services.values()]) if self.services else None
        }
    
    def export_health_report(self) -> Dict[str, Any]:
        """Export comprehensive health report"""
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'statistics': self.get_service_statistics(),
            'services': {}
        }
        
        for name, health in self.services.items():
            report['services'][name] = {
                'name': health.name,
                'url': health.url,
                'status': health.status.value,
                'last_check': health.last_check.isoformat(),
                'response_time_ms': round(health.response_time * 1000, 2) if health.response_time else None,
                'error': health.error,
                'consecutive_failures': health.consecutive_failures,
                'last_success': health.last_success.isoformat() if health.last_success else None,
                'required': health.metadata.get('required', False),
                'circuit_open': self.is_circuit_open(name)
            }
        
        return report
    
    def reset_service_failures(self, service_name: str):
        """Reset failure count for a service"""
        if service_name in self.services:
            self.services[service_name].consecutive_failures = 0
            logger.info(f"Reset failure count for service {service_name}")
    
    def force_service_check(self, service_name: str) -> bool:
        """Force immediate health check for a service"""
        return self.check_service_health(service_name)

# Global service discovery instance
service_discovery = ServiceDiscovery()

# Convenience functions
def get_service_url(service_name: str) -> Optional[str]:
    """Get URL for a healthy service"""
    return service_discovery.get_service_url(service_name)

def is_service_healthy(service_name: str) -> bool:
    """Check if a service is healthy"""
    return service_discovery.is_service_healthy(service_name)

def get_healthy_services() -> List[str]:
    """Get list of healthy services"""
    return service_discovery.get_healthy_services()

def start_service_monitoring():
    """Start service monitoring"""
    service_discovery.start_monitoring()

def stop_service_monitoring():
    """Stop service monitoring"""
    service_discovery.stop_monitoring()

