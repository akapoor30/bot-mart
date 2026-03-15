from sqlalchemy import Column, String, Integer, ForeignKey, JSON, DateTime, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum
from datetime import datetime

Base = declarative_base()

class PlatformName(enum.Enum):
    BLINKIT = "blinkit"
    ZEPTO = "zepto"
    INSTAMART = "instamart"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    keycloak_id = Column(String, unique=True, index=True, nullable=False) # Maps to Keycloak's UUID
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sessions = relationship("PlatformSession", back_populates="user", cascade="all, delete-orphan")

class PlatformSession(Base):
    __tablename__ = "platform_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    platform = Column(Enum(PlatformName), nullable=False)
    
    # Store the Playwright context cookies here
    auth_cookies = Column(JSON, nullable=False) 
    
    # Store the location contextual data
    location_lat = Column(String, nullable=True)
    location_lng = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")