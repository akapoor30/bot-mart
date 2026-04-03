# Re-export all models so imports like `from app.models import Base, User` work
# even though app/models/ is a directory (Python uses directory over .py file).

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
    keycloak_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sessions = relationship("PlatformSession", back_populates="user", cascade="all, delete-orphan")

class PlatformSession(Base):
    __tablename__ = "platform_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    platform = Column(Enum(PlatformName), nullable=False)
    auth_cookies = Column(JSON, nullable=False)
    location_lat = Column(String, nullable=True)
    location_lng = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="sessions")

class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # search_query is the original user query (e.g. "milk"), used for cross-platform matching
    search_query = Column(String, nullable=False)
    product_name = Column(String, nullable=True)  # Optional: specific product added
    quantity = Column(Integer, default=1)
    preferred_platform = Column(Enum(PlatformName), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", backref="cart_items")

class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    # search_query: the original user query that triggered this scrape (e.g. "milk")
    search_query = Column(String, index=True, nullable=False)
    product_name = Column(String, index=True, nullable=False)  # Platform-specific name
    platform = Column(Enum(PlatformName), nullable=False)
    pincode = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    delivery_fee = Column(Integer, default=0)
    handling_fee = Column(Integer, default=0)
    platform_fee = Column(Integer, default=0)
    gst_fee = Column(Integer, default=0)
    in_stock = Column(Integer, default=1)
    scraped_at = Column(DateTime, default=datetime.utcnow)
