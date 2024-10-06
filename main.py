from fastapi import FastAPI, Request, Form, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import crud, models, schemas
from formatting import format_money, format_date, format_percentage, format_number
from database import SessionLocal, engine
from pydantic import BaseModel

import math
import pandas as pd
import numpy as np
from typing import Optional, Annotated
from datetime import date, timedelta, datetime
import ast

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Jinja2Templates with the templates directory
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home():
    return templates.TemplateResponse('asset.html')

with open('preparation/initial_categories.txt', 'r') as category_file:
    initial_categories_txt = category_file.read()
initial_categories = ast.literal_eval(initial_categories_txt)

with open('preparation/initial_wallets.txt', 'r') as wallet_file:
    initial_wallets_txt = wallet_file.read()
initial_wallets = ast.literal_eval(initial_wallets_txt)

@app.post("/users/create", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    new_user = crud.create_user(db=db, user=user)
    crud.new_user_setup(db=db, wallet_list=initial_wallets, category_list=initial_categories, user_id=new_user.id)

    return new_user

@app.post("/users/update", response_model=schemas.User)
def update_user(user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db)):
    # Convert the UserUpdate schema to a dictionary
    update_data = user_update.model_dump(exclude_unset=True)
    
    db_user = crud.update_user(
        db=db,
        user_id=user_id,
        **update_data
    )
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return db_user

@app.post("/users/delete", response_model=schemas.User)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.delete_user(db=db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


templates.env.filters['format_number'] = format_number
templates.env.filters['format_percentage'] = format_percentage
templates.env.filters['format_date'] = format_date
templates.env.filters['format_money'] = format_money

user_id = 1
@app.get("/transactions", response_class=HTMLResponse, name="transactions")
def get_transaction_page(request: Request, db: Session = Depends(get_db),
                         page = 1,
                         category_id: Optional[int] = None,
                         wallet_id: Optional[int] = None,
                         transaction_type_id: Optional[int] = None,
                         date_from: Optional[str] = None,
                         date_to: Optional[str] = None):
    
    # change all id input to int
    if category_id: category_id = int(category_id)
    if wallet_id: wallet_id = int(wallet_id)
    if transaction_type_id: transaction_type_id = int(transaction_type_id)
    page = int(page)

    # change date input to datetime
    if date_from: date_from = datetime.fromisoformat(date_from)
    if date_to: date_to = datetime.fromisoformat(date_to)

    username = crud.get_user(db, user_id=user_id).username
    categories = crud.get_categories(db, user_id=user_id)
    wallets = crud.get_wallets(db, user_id=user_id)
    transaction_types = crud.get_transaction_types(db)
    transactions = crud.get_transactions(db, user_id=user_id,
                                         wallet_id=wallet_id,
                                         category_id=category_id,
                                         transaction_type_id=transaction_type_id,
                                         transaction_date_from=date_from,
                                         transaction_date_to=date_to)

    # Pagination
    pagelimit = 10
    pages = math.ceil(len(transactions) / pagelimit)

    if page < 1: page = 1
    if page > pages: page = pages
    fromtrans = (page - 1) * pagelimit
    totrans = page * pagelimit
    transactions_offset = transactions[fromtrans : totrans]
    pagination = {'page': page, 'pages': pages, 'total': len(transactions), 'fromtrans': fromtrans, 'totrans': totrans}
    
    unique_options = {'categories': [{id: {x.id: x.category_name for x in categories}[id]} for id in set(transaction.category_id for transaction in transactions)],
                      'wallets': [{id: {x.id: x.wallet_name for x in wallets}[id]} for id in set(transaction.wallet_id for transaction in transactions)],
                      'transaction_types': [{id: {x.id: x.transaction_type_name for x in transaction_types}[id]} for id in set(transaction.transaction_type_id for transaction in transactions)]}
    return templates.TemplateResponse('transactions.html', 
                                      {'request': request,
                                       'username': username,
                                       'transactions': transactions_offset,
                                       'options': unique_options,
                                       'pagination': pagination})
