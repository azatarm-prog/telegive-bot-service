"""
Comprehensive monitoring utilities for Telegive Bot Service
Provides metrics collection, alerting, and observability features
"""

import time
import psutil
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics
import logging
from utils.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class Metric:
    """Represents a single metric measurement"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""

@dataclass
class Alert:
    """Represents an alert condition"""
    name: str
    condition: Callable[[float], bool]
    message: str
    severity: str = "WARNING"  # INFO, WARNING, ERROR, CRITICAL
    cooldown_seconds: int = 300  # 5 minutes
    last_triggered: Optional[datetime] = None

class MetricsCollector:
    """Collects and stores application metrics"""
    
    def __init__(self, max_metrics: int = 10000):
        self.metrics: deque = deque(maxlen=max_metrics)
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def counter(self, name: str, value: int = 1, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        with self._lock:
            key = self._make_key(name, tags)
            self.counters[key] += value
            
            metric = Metric(
                name=name,
                value=self.counters[key],
                timestamp=datetime.now(timezone.utc),
                tags=tags or {},
                unit="count"
            )
            self.metrics.append(metric)
            
            logger.debug(f"Counter {name}: {self.counters[key]}", extra={
                'component': 'metrics',
                'metric_type': 'counter',
                'metric_name': name,
                'metric_value': self.counters[key],
                'tags': tags
            })
    
    def gauge(self, name: str, value: float, tags: Dict[str, str] = None, unit: str = ""):
        """Set a gauge metric"""
        with self._lock:
            key = self._make_key(name, tags)
            self.gauges[key] = value
            
            metric = Metric(
                name=name,
                value=value,
                timestamp=datetime.now(timezone.utc),
                tags=tags or {},
                unit=unit
            )
            self.metrics.append(metric)
            
            logger.debug(f"Gauge {name}: {value}{unit}", extra={
                'component': 'metrics',
                'metric_type': 'gauge',
                'metric_name': name,
                'metric_value': value,
                'tags': tags
            })
    
    def histogram(self, name: str, value: float, tags: Dict[str, str] = None, unit: str = ""):
        """Add a value to a histogram metric"""
        with self._lock:
            key = self._make_key(name, tags)
            self.histograms[key].append(value)
            
            metric = Metric(
                name=name,
                value=value,
                timestamp=datetime.now(timezone.utc),
                tags=tags or {},
                unit=unit
            )
            self.metrics.append(metric)
    
    def timer(self, name: str, duration: float, tags: Dict[str, str] = None):
        """Record a timer metric"""
        with self._lock:
            key = self._make_key(name, tags)
            self.timers[key].append(duration)
            
            # Keep only last 1000 measurements
            if len(self.timers[key]) > 1000:
                self.timers[key] = self.timers[key][-1000:]
            
            metric = Metric(
                name=name,
                value=duration,
                timestamp=datetime.now(timezone.utc),
                tags=tags or {},
                unit="ms"
            )
            self.metrics.append(metric)
    
    def _make_key(self, name: str, tags: Dict[str, str] = None) -> str:
        """Create a unique key for metric storage"""
        if not tags:
            return name
        
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def get_counter(self, name: str, tags: Dict[str, str] = None) -> int:
        """Get current counter value"""
        key = self._make_key(name, tags)
        return self.counters.get(key, 0)
    
    def get_gauge(self, name: str, tags: Dict[str, str] = None) -> Optional[float]:
        """Get current gauge value"""
        key = self._make_key(name, tags)
        return self.gauges.get(key)
    
    def get_histogram_stats(self, name: str, tags: Dict[str, str] = None) -> Dict[str, float]:
        """Get histogram statistics"""
        key = self._make_key(name, tags)
        values = list(self.histograms.get(key, []))
        
        if not values:
            return {}
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'p95': self._percentile(values, 95),
            'p99': self._percentile(values, 99)
        }
    
    def get_timer_stats(self, name: str, tags: Dict[str, str] = None) -> Dict[str, float]:
        """Get timer statistics"""
        key = self._make_key(name, tags)
        values = list(self.timers.get(key, []))
        
        if not values:
            return {}
        
        return {
            'count': len(values),
            'min_ms': min(values),
            'max_ms': max(values),
            'mean_ms': statistics.mean(values),
            'median_ms': statistics.median(values),
            'p95_ms': self._percentile(values, 95),
            'p99_ms': self._percentile(values, 99)
        }
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100.0) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
    
    def get_all_metrics(self) -> List[Metric]:
        """Get all collected metrics"""
        with self._lock:
            return list(self.metrics)
    
    def clear_metrics(self):
        """Clear all collected metrics"""
        with self._lock:
            self.metrics.clear()
            self.counters.clear()
            self.gauges.clear()
            self.histograms.clear()
            self.timers.clear()

class SystemMonitor:
    """Monitors system resources and performance"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self._monitoring = False
        self._thread = None
        self.interval = 30  # seconds
    
    def start_monitoring(self):
        """Start system monitoring"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("System monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self._monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                time.sleep(5)
    
    def _collect_system_metrics(self):
        """Collect system performance metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics.gauge('system.cpu.usage_percent', cpu_percent, unit='%')
            
            cpu_count = psutil.cpu_count()
            self.metrics.gauge('system.cpu.count', cpu_count)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            self.metrics.gauge('system.memory.total_bytes', memory.total, unit='bytes')
            self.metrics.gauge('system.memory.available_bytes', memory.available, unit='bytes')
            self.metrics.gauge('system.memory.used_bytes', memory.used, unit='bytes')
            self.metrics.gauge('system.memory.usage_percent', memory.percent, unit='%')
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            self.metrics.gauge('system.disk.total_bytes', disk.total, unit='bytes')
            self.metrics.gauge('system.disk.free_bytes', disk.free, unit='bytes')
            self.metrics.gauge('system.disk.used_bytes', disk.used, unit='bytes')
            self.metrics.gauge('system.disk.usage_percent', (disk.used / disk.total) * 100, unit='%')
            
            # Network metrics
            network = psutil.net_io_counters()
            self.metrics.counter('system.network.bytes_sent', network.bytes_sent)
            self.metrics.counter('system.network.bytes_recv', network.bytes_recv)
            self.metrics.counter('system.network.packets_sent', network.packets_sent)
            self.metrics.counter('system.network.packets_recv', network.packets_recv)
            
            # Process metrics
            process = psutil.Process()
            self.metrics.gauge('process.memory.rss_bytes', process.memory_info().rss, unit='bytes')
            self.metrics.gauge('process.memory.vms_bytes', process.memory_info().vms, unit='bytes')
            self.metrics.gauge('process.cpu.usage_percent', process.cpu_percent(), unit='%')
            self.metrics.gauge('process.threads.count', process.num_threads())
            
            # File descriptors (Unix only)
            try:
                self.metrics.gauge('process.fd.count', process.num_fds())
            except AttributeError:
                pass  # Windows doesn't have num_fds
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

class AlertManager:
    """Manages alerts and notifications"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.alerts: Dict[str, Alert] = {}
        self.alert_handlers: List[Callable[[Alert, float], None]] = []
        self._monitoring = False
        self._thread = None
        self.check_interval = 60  # seconds
    
    def add_alert(self, alert: Alert):
        """Add an alert condition"""
        self.alerts[alert.name] = alert
        logger.info(f"Alert added: {alert.name}")
    
    def add_alert_handler(self, handler: Callable[[Alert, float], None]):
        """Add an alert handler function"""
        self.alert_handlers.append(handler)
    
    def start_monitoring(self):
        """Start alert monitoring"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Alert monitoring started")
    
    def stop_monitoring(self):
        """Stop alert monitoring"""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Alert monitoring stopped")
    
    def _monitor_loop(self):
        """Main alert monitoring loop"""
        while self._monitoring:
            try:
                self._check_alerts()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in alert monitoring: {e}")
                time.sleep(5)
    
    def _check_alerts(self):
        """Check all alert conditions"""
        current_time = datetime.now(timezone.utc)
        
        for alert_name, alert in self.alerts.items():
            try:
                # Get the latest gauge value for the alert
                # This is a simplified implementation - in practice you'd want more sophisticated metric querying
                metric_value = self.metrics.get_gauge(alert_name)
                
                if metric_value is not None and alert.condition(metric_value):
                    # Check cooldown
                    if (alert.last_triggered is None or 
                        (current_time - alert.last_triggered).total_seconds() >= alert.cooldown_seconds):
                        
                        alert.last_triggered = current_time
                        self._trigger_alert(alert, metric_value)
                        
            except Exception as e:
                logger.error(f"Error checking alert {alert_name}: {e}")
    
    def _trigger_alert(self, alert: Alert, value: float):
        """Trigger an alert"""
        logger.warning(f"Alert triggered: {alert.name} - {alert.message} (value: {value})", extra={
            'component': 'alerting',
            'alert_name': alert.name,
            'alert_severity': alert.severity,
            'metric_value': value
        })
        
        # Call all alert handlers
        for handler in self.alert_handlers:
            try:
                handler(alert, value)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")

class PerformanceMonitor:
    """Monitors application performance"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
    
    def time_function(self, func_name: str, tags: Dict[str, str] = None):
        """Decorator to time function execution"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    success = True
                    error = None
                except Exception as e:
                    success = False
                    error = e
                    raise
                finally:
                    duration = (time.time() - start_time) * 1000  # Convert to milliseconds
                    
                    # Record timing
                    timing_tags = (tags or {}).copy()
                    timing_tags['function'] = func_name
                    timing_tags['success'] = str(success)
                    
                    self.metrics.timer('function.execution_time', duration, timing_tags)
                    
                    # Record call count
                    self.metrics.counter('function.calls', 1, timing_tags)
                    
                    if error:
                        error_tags = timing_tags.copy()
                        error_tags['error_type'] = type(error).__name__
                        self.metrics.counter('function.errors', 1, error_tags)
                
                return result
            return wrapper
        return decorator
    
    def record_request_metrics(self, method: str, path: str, status_code: int, duration: float):
        """Record HTTP request metrics"""
        tags = {
            'method': method,
            'path': path,
            'status_code': str(status_code),
            'status_class': f"{status_code // 100}xx"
        }
        
        self.metrics.counter('http.requests', 1, tags)
        self.metrics.timer('http.request_duration', duration * 1000, tags)  # Convert to ms
        
        if status_code >= 400:
            self.metrics.counter('http.errors', 1, tags)
    
    def record_database_metrics(self, operation: str, table: str, duration: float, success: bool):
        """Record database operation metrics"""
        tags = {
            'operation': operation,
            'table': table,
            'success': str(success)
        }
        
        self.metrics.counter('database.operations', 1, tags)
        self.metrics.timer('database.operation_duration', duration * 1000, tags)
        
        if not success:
            self.metrics.counter('database.errors', 1, tags)
    
    def record_external_service_metrics(self, service: str, endpoint: str, status_code: int, duration: float):
        """Record external service call metrics"""
        tags = {
            'service': service,
            'endpoint': endpoint,
            'status_code': str(status_code),
            'success': str(status_code < 400)
        }
        
        self.metrics.counter('external_service.calls', 1, tags)
        self.metrics.timer('external_service.duration', duration * 1000, tags)
        
        if status_code >= 400:
            self.metrics.counter('external_service.errors', 1, tags)

class MonitoringManager:
    """Central monitoring management"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.system_monitor = SystemMonitor(self.metrics_collector)
        self.alert_manager = AlertManager(self.metrics_collector)
        self.performance_monitor = PerformanceMonitor(self.metrics_collector)
        
        self._setup_default_alerts()
    
    def _setup_default_alerts(self):
        """Setup default system alerts"""
        # High CPU usage
        self.alert_manager.add_alert(Alert(
            name="system.cpu.usage_percent",
            condition=lambda x: x > 80,
            message="High CPU usage detected",
            severity="WARNING",
            cooldown_seconds=300
        ))
        
        # High memory usage
        self.alert_manager.add_alert(Alert(
            name="system.memory.usage_percent",
            condition=lambda x: x > 85,
            message="High memory usage detected",
            severity="WARNING",
            cooldown_seconds=300
        ))
        
        # High disk usage
        self.alert_manager.add_alert(Alert(
            name="system.disk.usage_percent",
            condition=lambda x: x > 90,
            message="High disk usage detected",
            severity="CRITICAL",
            cooldown_seconds=600
        ))
    
    def start_monitoring(self):
        """Start all monitoring components"""
        self.system_monitor.start_monitoring()
        self.alert_manager.start_monitoring()
        logger.info("Monitoring started")
    
    def stop_monitoring(self):
        """Stop all monitoring components"""
        self.system_monitor.stop_monitoring()
        self.alert_manager.stop_monitoring()
        logger.info("Monitoring stopped")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics"""
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system': {
                'cpu_usage': self.metrics_collector.get_gauge('system.cpu.usage_percent'),
                'memory_usage': self.metrics_collector.get_gauge('system.memory.usage_percent'),
                'disk_usage': self.metrics_collector.get_gauge('system.disk.usage_percent'),
            },
            'application': {
                'http_requests': self.metrics_collector.get_counter('http.requests'),
                'http_errors': self.metrics_collector.get_counter('http.errors'),
                'database_operations': self.metrics_collector.get_counter('database.operations'),
                'database_errors': self.metrics_collector.get_counter('database.errors'),
            },
            'performance': {
                'http_request_duration': self.metrics_collector.get_timer_stats('http.request_duration'),
                'database_operation_duration': self.metrics_collector.get_timer_stats('database.operation_duration'),
            }
        }

# Global monitoring manager
monitoring_manager = MonitoringManager()

# Convenience functions
def start_monitoring():
    """Start monitoring"""
    monitoring_manager.start_monitoring()

def stop_monitoring():
    """Stop monitoring"""
    monitoring_manager.stop_monitoring()

def get_metrics_collector() -> MetricsCollector:
    """Get metrics collector instance"""
    return monitoring_manager.metrics_collector

def get_performance_monitor() -> PerformanceMonitor:
    """Get performance monitor instance"""
    return monitoring_manager.performance_monitor

def get_alert_manager() -> AlertManager:
    """Get alert manager instance"""
    return monitoring_manager.alert_manager

