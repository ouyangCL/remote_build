"""Initialize database."""
import sys
sys.path.insert(0, '.')

from app.db.session import ensure_directories
from app.models.base import Base

# Ensure directories exist
ensure_directories()

# Create all tables
from app.db.session import engine
Base.metadata.create_all(bind=engine)

print("Database initialized successfully!")
print("Tables created:")
for table in Base.metadata.tables.keys():
    print(f"  - {table}")
