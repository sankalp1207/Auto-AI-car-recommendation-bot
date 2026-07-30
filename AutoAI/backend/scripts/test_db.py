from app.database.database import Base, engine
from app.models.car import Car

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done!")

print(Base.metadata.tables.keys())