from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    fullname = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    currency = Column(String)
    is_active = Column(Boolean, default=1)
    registered_date = Column(DateTime, default=datetime.now)
    updated_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    categorys = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    wallet_name = Column(String)
    description = Column(String)
    liability = Column(Integer)
    initial_balance = Column(Float)

    user = relationship("User", back_populates="wallets")
    transaction = relationship("Transaction", back_populates="wallet", cascade="all, delete-orphan")

class TransactionType(Base):
    __tablename__ = "transaction_types"
    id = Column(Integer, primary_key=True, index=True)
    transaction_type_name = Column(String)

    category = relationship("Category", back_populates="transaction_type")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    transaction_type_id = Column(Integer, ForeignKey("transaction_types.id"))
    category_name = Column(String)
    description = Column(String)
    created_date = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="categorys")
    transaction_type = relationship("TransactionType", back_populates="category")
    transaction = relationship("Transaction", back_populates="category", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    wallet_id = Column(Integer, ForeignKey("wallets.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    transaction_type_id = Column(Integer, ForeignKey("transaction_types.id"))
    amount = Column(Float)
    description = Column(String)
    transaction_date = Column(DateTime)
    created_date = Column(DateTime, default=datetime.now)
    updated_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="transactions")
    wallet = relationship("Wallet", back_populates="transaction")
    category = relationship("Category", back_populates="transaction")
    transaction_type = relationship("TransactionType")
