import sys
import bcrypt
sys.path.insert(0, '.')

from sqlalchemy.orm import Session
from app.db.session import engine
from app.models.user import User, UserRole

db = Session(engine)

admin = db.query(User).first()
if not admin:
    password = b"admin123"
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())
    admin = User(
        username="admin",
        hashed_password=hashed.decode(),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    print("Admin user created: admin / admin123")
else:
    print(f"Admin already exists: {admin.username}")

db.close()
