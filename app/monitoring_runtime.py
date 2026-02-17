from app.services.monitoring import DomainMonitoringService
from app.state import store

monitoring_service = DomainMonitoringService(store)
