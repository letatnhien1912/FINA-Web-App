from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from fastapi import HTTPException

import app.models as models, app.schemas as schemas

### User functions
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(and_(models.User.username == username)).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(and_(models.User.email == email, models.User.is_active == 1)).first()

def get_users(db: Session):
    return db.query(models.User).all()

def update_user(db: Session,
                user_id: int,
                username: str = None,
                fullname: str = None,
                email: str = None,
                currency: str = None,
                is_active: bool = True):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    users = get_users(db)
    emails = [user.email for user in users if user.id != user_id]
    usernames = [user.username for user in users if user.id != user_id]
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if email is not None and email != '':
        if email in emails:
            raise HTTPException(status_code=400, detail="Email already exists")
        db_user.email = email
    if username is not None:
        if username in usernames:
            raise HTTPException(status_code=400, detail="Username already exists")
        db_user.username = username
    if fullname is not None:
        db_user.fullname = fullname
    if currency is not None:
        db_user.currency = currency
    if is_active is not None:
        db_user.is_active = is_active
    
    db.commit()
    db.refresh(db_user)
    return db_user

def inactive_user(db: Session, user_id: int):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        return ValueError("User not found")
    
    db_user.is_active = 0
    db.commit()
    return db_user

def delete_user(db: Session, user_id: int):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        return ValueError("User not found")
    
    db.delete(db_user)
    db.commit()
    return db_user

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = generate_password_hash(user.password)
    db_user = models.User(username=user.username,
                          fullname=user.fullname,
                          email=user.email,
                          hashed_password=hashed_password,
                          is_active=1,
                          currency=user.currency)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def verify_password(db: Session, user, password: str):
    if not user.hashed_password:
        return False
    return check_password_hash(user.hashed_password, password)

def reset_password(db: Session, user_id: int, new_password: str):
    hashed_password = generate_password_hash(new_password)
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        return ValueError("User not found")
    db_user.hashed_password = hashed_password
    db.commit()
    db.refresh(db_user)
    return db_user

### Wallet functions
def get_wallets(db: Session, user_id: int, liability=None):
    if liability is not None:
        return db.query(models.Wallet).filter(and_(models.Wallet.user_id == user_id, models.Wallet.liability == liability)).all()
    
    return db.query(models.Wallet).filter(models.Wallet.user_id == user_id).all()

def get_wallet_by_name(db: Session, user_id: int, wallet_name: str):
    return db.query(models.Wallet).filter(and_(models.Wallet.user_id == user_id, models.Wallet.wallet_name == wallet_name)).first()

def get_wallet_by_id(db: Session, wallet_id: int):
    return db.query(models.Wallet).filter(models.Wallet.id == wallet_id).first()

def create_wallet(db: Session, user_id: int, wallet_name: str, liability: int = 0, description: str = None, initial_balance: float = 0):
    existing_wallet = db.query(models.Wallet).filter(and_(models.Wallet.user_id == user_id, models.Wallet.wallet_name == wallet_name)).first()
    if existing_wallet:
        return ValueError("Wallet exists")
    
    db_wallet = models.Wallet(user_id=user_id,
                            wallet_name=wallet_name,
                            description=description,
                            liability=liability,
                            initial_balance=initial_balance)
    db.add(db_wallet)
    db.commit()
    db.refresh(db_wallet)
    return db_wallet

def update_wallet(db: Session, wallet_id: int, wallet_name: str = None, description: str = None, initial_balance: float = None):
    db_wallet = db.query(models.Wallet).filter(models.Wallet.id==wallet_id).first()
    if db_wallet is None:
        return ValueError("Wallet not found")
    if wallet_name is not None:
        db_wallet.wallet_name = wallet_name
    if description is not None:
        db_wallet.description = description
    if initial_balance is not None:
        db_wallet.initial_balance = initial_balance
    db.commit()
    db.refresh(db_wallet)
    return db_wallet

def delete_wallet(db: Session, wallet_id: int):
    db_wallet = db.query(models.Wallet).filter(models.Wallet.id==wallet_id).first()
    if db_wallet is None:
        return ValueError("Wallet not found")
    db.delete(db_wallet)
    db.commit()
    return db_wallet

### Category functions
def get_categories(db: Session, user_id: int, transaction_type_id: int = None):
    query = db.query(models.Category).filter(models.Category.user_id == user_id)

    if transaction_type_id is not None:
        query = query.filter(models.Category.transaction_type_id == transaction_type_id)
    
    return query.all()

def create_category(db: Session,
                    user_id: int,
                    transaction_type_id: int,
                    category_name: str,
                    description: str = None):
    db_category = models.Category(user_id=user_id,
                              transaction_type_id=transaction_type_id,
                              category_name=category_name,
                              description=description)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def update_category(db: Session,
                    category_id: int,
                    user_id: int = None,
                    transaction_type_id: int = None,
                    category_name: str = None,
                    description: str = None):

    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()

    if db_category is None:
        return ValueError("Category not found")

    # Update the fields if new values are provided
    if user_id is not None:
        db_category.user_id = user_id
    if transaction_type_id is not None:
        db_category.transaction_type_id = transaction_type_id
    if category_name is not None:
        db_category.category_name = category_name
    if description is not None:
        db_category.description = description

    db.commit()
    db.refresh(db_category)

    return db_category

def delete_category(db: Session, category_id: int):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if db_category is None:
        return ValueError("Category not found")
    db.delete(db_category)
    db.commit()
    return db_category

# Transcation functions
def get_transactions(db: Session,
                     user_id: int,
                     wallet_id: list = None,
                     category_id: int = None,
                     transaction_type_id: int = None,
                     transaction_date: datetime = None,
                     transaction_date_from: datetime = None,
                     transaction_date_to: datetime = None):
    query = db.query(models.Transaction).filter(models.Transaction.user_id == user_id)
    
    if wallet_id is not None:
        query = query.filter(models.Transaction.wallet_id == wallet_id)
    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)
    if transaction_type_id is not None:
        query = query.filter(models.Transaction.transaction_type_id == transaction_type_id)
    if transaction_date is not None:
        query = query.filter(models.Transaction.transaction_date == transaction_date)
    if transaction_date_from is not None:
        query = query.filter(models.Transaction.transaction_date >= transaction_date_from)
    if transaction_date_to is not None:
        query = query.filter(models.Transaction.transaction_date <= transaction_date_to)
    
    query = query.order_by(desc(models.Transaction.transaction_date))
    
    return query.all()

def create_transaction(db: Session,
                       user_id: int,
                       wallet_id: int,
                       category_id: int,
                       transaction_type_id: int,
                       amount: float,
                       transaction_date: datetime,
                       description: str = None):
    transaction_type_categories = get_categories(db=db, user_id=user_id, transaction_type_id=transaction_type_id)
    if transaction_type_id in [1,2] and category_id not in [category.id for category in transaction_type_categories]:
        raise HTTPException(detail="Invalid category or transaction type", status_code=400)
    
    db_transaction = models.Transaction(user_id=user_id,
                                   wallet_id=wallet_id,
                                   category_id=category_id,
                                   transaction_type_id=transaction_type_id,
                                   amount=amount,
                                   transaction_date=transaction_date,
                                   description=description)
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def update_transaction(db: Session,
                       transaction_id: int,
                       user_id: int = None,
                       wallet_id: int = None,
                       category_id: int = None,
                       transaction_type_id = None,
                       amount: float = None,
                       transaction_date: datetime = None,
                       description: str = None):

    db_transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()

    if db_transaction is None:
        return ValueError("Transaction not found")

    if transaction_type_id is not None and category_id is not None:
        db_category = db.query(models.Category).filter(models.Category.id == category_id, models.Category.transaction_type_id == transaction_type_id).first()
        if db_category is None:
            raise ValueError("Invalid category or transaction type")

    # Update the fields if new values are provided
    if user_id is not None:
        db_transaction.user_id = user_id
    if wallet_id is not None:
        db_transaction.wallet_id = wallet_id
    if category_id is not None:
        db_transaction.category_id = category_id
    if transaction_type_id is not None:
        db_transaction.transaction_type_id = transaction_type_id
    if amount is not None:
        db_transaction.amount = amount
    if transaction_date is not None:
        db_transaction.transaction_date = transaction_date
    if description is not None:
        db_transaction.description = description

    db.commit()
    db.refresh(db_transaction)

    return db_transaction

def delete_transaction(db: Session, transaction_id: int):
    db_transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if db_transaction is None:
        return ValueError("Transaction not found")
    db.delete(db_transaction)
    db.commit()
    return db_transaction

def new_user_setup(db: Session,
                   wallet_list: list,
                   category_list: list,
                   user_id: int):
    # Setup intial wallets
    for wallet in wallet_list:
        db_wallet = models.Wallet(user_id=user_id, wallet_name=wallet[0], description=wallet[1], liability=wallet[2], initial_balance=0)
        db.add(db_wallet)
    
    # Setup intial categories
    for category in category_list:
        db_category = models.Category(user_id=user_id,
                                      category_name=category[0],
                                      transaction_type_id=category[1],
                                      description=category[2])
        db.add(db_category)

    db.commit()
    db.refresh(db_wallet)
    db.refresh(db_category)

    return True

def get_transaction_types(db: Session, ie=False):
    if ie:
        return db.query(models.TransactionType).filter(models.TransactionType.id.in_([1, 2])).all()
    return db.query(models.TransactionType).all()
