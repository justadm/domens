from app.config import settings
from app.services.store import PostgresStore

store = PostgresStore(settings.postgres_dsn)
