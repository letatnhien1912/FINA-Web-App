from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

### wallets table
class WalletBase(BaseModel):
    wallet_name: str
    description: str
    liability: int

class Wallet(WalletBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

### transaction_types table
class TransactionTypeBase(BaseModel):
    transaction_type_name: str

class TransactionType(TransactionTypeBase):
    id: int

### categories table
class CategoryBase(BaseModel):
    category_name: str
    description: str
    created_date: datetime

class Category(CategoryBase):
    id: int
    user_id: int
    transaction_type_id: int

    class Config:
        from_attributes = True

### transactions table
class TransactionBase(BaseModel):
    amount: float
    description: str
    transaction_date: datetime
    created_date: datetime
    updated_date: datetime

class Transaction(TransactionBase):
    id: int
    user_id: int
    wallet_id: int
    category_id: int
    transaction_type_id: int

    class Config:
        from_attributes = True

### users table
class UserBase(BaseModel):
    username: str
    registered_date: datetime
    updated_date: datetime

class UserUpdate(BaseModel):
    username: Optional[str] = None
    is_active: Optional[bool] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    wallet: list[Wallet] = []
    category: list[Category] = []
    transaction: list[Transaction] = []

    class Config:
        from_attributes = True

