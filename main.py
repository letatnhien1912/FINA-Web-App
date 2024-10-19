from fastapi import FastAPI, Request, Form, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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

@app.get("/", response_class=HTMLResponse)
async def read_home(request: Request, db: Session = Depends(get_db)):

    user_id = request.cookies.get("user_id")
    if not user_id:
        return templates.TemplateResponse("login.html", {"request": request})

    return RedirectResponse(url="/transactions", status_code=303)

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
    db_user = crud.inactive_user(db=db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


templates.env.filters['format_number'] = format_number
templates.env.filters['format_percentage'] = format_percentage
templates.env.filters['format_date'] = format_date
templates.env.filters['format_money'] = format_money

### Transactions Routes
@app.get("/transactions", response_class=HTMLResponse, name="transactions")
async def get_transaction_page(request: Request, db: Session = Depends(get_db),
                         page = 1,
                         transaction_type_id: Optional[str] = None,
                         category_id: Optional[str] = None,
                         wallet_id: Optional[str] = None,
                         startdate: Optional[str] = None,
                         enddate: Optional[str] = None,
                         error: Optional[str] = None):
    
    user_id = request.cookies.get("user_id")

    # change all id input to int
    if category_id: category_id = int(category_id)
    if wallet_id: wallet_id = int(wallet_id)
    if transaction_type_id: transaction_type_id = int(transaction_type_id)
    page = int(page)
    
    # change date input to datetime
    if startdate: startdate = datetime.fromisoformat(startdate)
    if enddate: enddate = datetime.fromisoformat(enddate)

    user = crud.get_user(db, user_id=user_id)
    username = user.fullname
    categories = crud.get_categories(db, user_id=user_id)
    wallets = crud.get_wallets(db, user_id=user_id, liability=0)
    debtors = crud.get_wallets(db, user_id=user_id, liability=1)
    transaction_types = crud.get_transaction_types(db, ie=True)
    transactions = crud.get_transactions(db, user_id=user_id,
                                         wallet_id=wallet_id,
                                         category_id=category_id,
                                         transaction_type_id=transaction_type_id,
                                         transaction_date_from=startdate,
                                         transaction_date_to=enddate)
    
    all_options = {'categories': [{'id': category.id, 'name': category.category_name} for category in categories],
                   'wallets': [{'id': wallet.id, 'name': wallet.wallet_name} for wallet in wallets],
                   'transaction_types': [{'id': transaction_type.id, 'name': transaction_type.transaction_type_name} for transaction_type in transaction_types],
                   'debtors': [] if len(debtors) == 0 else [{'id': debtor.id, 'name': debtor.wallet_name} for debtor in debtors]}

    filter_options = {'categories': [{x.id: x.category_name} for x in categories if x.id in set(transaction.category_id for transaction in transactions)],
                'wallets': [{x.id: x.wallet_name} for x in wallets if x.id in set(transaction.wallet_id for transaction in transactions)],
                'transaction_types': [{x.id: x.transaction_type_name} for x in transaction_types if x.id in set(transaction.transaction_type_id for transaction in transactions)]}
    
    # Handle case no records
    if len(transactions) == 0:
        return templates.TemplateResponse('transactions.html', 
                                      {'request': request,
                                       'username': username,
                                       'transactions': None,
                                       'options': filter_options,
                                       'all_options': all_options,
                                       'pagination': None,
                                       'error': "No records found"})
    
    # Pagination
    pagelimit = 10
    pages = math.ceil(len(transactions) / pagelimit)

    if page < 1: page = 1
    if page > pages: page = pages
    fromtrans = (page - 1) * pagelimit
    totrans = page * pagelimit
    transactions_offset = transactions[fromtrans : totrans]
    pagination = {'page': page, 'pages': pages, 'total': len(transactions), 'fromtrans': fromtrans + 1, 'totrans': totrans}
    
    return templates.TemplateResponse('transactions.html', 
                                      {'request': request,
                                       'username': username,
                                       'transactions': transactions_offset,
                                       'options': filter_options,
                                       'all_options': all_options,
                                       'pagination': pagination,
                                       'error': error})

@app.post("/transactions/create")
async def add_transaction(request: Request,
                    selected_date: Annotated[str, Form()],
                    selected_type: Annotated[str, Form()],
                    category: Annotated[str, Form()],
                    wallet: Annotated[str, Form()],
                    amount: Annotated[float, Form()],
                    description: Annotated[str, Form()],
                    db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    selected_date = datetime.fromisoformat(selected_date).date()
    wallet_id = int(wallet)
    category_id = int(category)
    transaction_type_id = int(selected_type)
    crud.create_transaction(db=db,
                            user_id=user_id,
                            wallet_id=wallet_id,
                            category_id=category_id,
                            transaction_type_id=transaction_type_id,
                            amount=amount,
                            transaction_date=selected_date,
                            description=description)
    return RedirectResponse(url="/transactions", status_code=303)

@app.post("/transactions/create/transfer")
async def add_debt(request: Request,
                    selected_date: Annotated[str, Form()],
                    category: Annotated[int, Form()],
                    selected_type: Annotated[int, Form()],
                    wallet: Annotated[str, Form()],
                    wallet_to: Annotated[str, Form()],
                    amount: Annotated[float, Form()],
                    description: Annotated[str, Form()],
                    db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    selected_date = datetime.fromisoformat(selected_date).date()
    wallet_from = int(wallet)
    transaction_type_id = int(selected_type)

    # Create debt wallet if it doesn't exist
    if transaction_type_id==4:
        wallet_to_first = crud.get_wallet_by_name(db=db, user_id=user_id, wallet_name=wallet_to)
        if not wallet_to_first:
            crud.create_wallet(db=db, user_id=user_id, wallet_name=wallet_to, liability=1)
            wallet_to_first = crud.get_wallet_by_name(db=db, user_id=user_id, wallet_name=wallet_to)

    print(wallet_to_first.id, wallet_to_first.wallet_name)
    # Create 2 transactions for the debt
    ## Create first transaction
    crud.create_transaction(db=db,
                            user_id=user_id,
                            wallet_id=wallet_from,
                            category_id=None,
                            transaction_type_id=transaction_type_id,
                            amount=amount if category == 0 else -amount,
                            transaction_date=selected_date,
                            description=description)
    ## Create second transaction
    crud.create_transaction(db=db,
                            user_id=user_id,
                            wallet_id=wallet_to_first.id,
                            category_id=None,
                            transaction_type_id=transaction_type_id,
                            amount=-amount if category == 0 else amount,
                            transaction_date=selected_date,
                            description=description)

    return RedirectResponse(url="/transactions", status_code=303)

@app.post("/transactions/update")
async def update_transaction(request: Request,
                    transaction_id: Annotated[int, Form()],
                    selected_date: Annotated[str, Form()],
                    selected_type: Annotated[str, Form()],
                    category: Annotated[str, Form()],
                    wallet: Annotated[str, Form()],
                    amount: Annotated[float, Form()],
                    description: Annotated[str, Form()],
                    db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    selected_date = datetime.fromisoformat(selected_date).date()
    wallet_id = int(wallet)
    category_id = int(category)
    transaction_type_id = int(selected_type)

    try:
        crud.update_transaction(db = db,
                                transaction_id = transaction_id,
                                wallet_id = wallet_id,
                                category_id = category_id,
                                transaction_type_id = transaction_type_id,
                                amount = amount,
                                transaction_date = selected_date,
                                description = description)

        return RedirectResponse(url="/transactions", status_code=303)
    except ValueError:
        return ValueError("Invalid category or transaction type", status_code=400)

class deleteTransactionRequest(BaseModel):
    transaction_id: int
@app.post("/transactions/delete")
async def delete_transaction(request: deleteTransactionRequest, db: Session = Depends(get_db)):
    crud.delete_transaction(db=db, transaction_id=request.transaction_id)
    return RedirectResponse(url="/transactions", status_code=303)

### Wallets Routes
@app.get('/wallets')
async def get_wallets(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    username = crud.get_user(db, user_id=user_id).fullname
    wallets = crud.get_wallets(db, user_id=user_id, liability=0)
    debts = crud.get_wallets(db, user_id=user_id, liability=1)
    return templates.TemplateResponse('wallets.html', 
                                      {'request': request,
                                       'username': username,
                                       'wallets': wallets,
                                       'debts': debts})

@app.post("/wallets/create")
async def add_wallet(request: Request,
                wallet: Annotated[str, Form()],
               description: Annotated[str, Form()],
               db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    try:
        crud.create_wallet(db=db, user_id=user_id, wallet_name=wallet, description=description)
        return RedirectResponse(url="/wallets", status_code=303)
    except ValueError:
        return ValueError("Invalid wallet name", status_code=400)

@app.post("/wallets/update")
async def update_wallet(wallet_id: Annotated[int, Form()],
                  wallet: Annotated[str, Form()],
                  description: Annotated[str, Form()],
                  db: Session = Depends(get_db)):
    try:
        crud.update_wallet(db=db,
                           wallet_id=wallet_id,
                           wallet_name=wallet,
                           description=description)
        return RedirectResponse(url="/wallets", status_code=303)
    except ValueError:
        return ValueError("Invalid wallet id", status_code=400)

class deleteWalletRequest(BaseModel):
    wallet_id: int
@app.post("/wallets/delete")
async def delete_wallet(request: deleteWalletRequest,
                  db: Session = Depends(get_db)):
    try:
        crud.delete_wallet(db=db, wallet_id=request.wallet_id)
        return RedirectResponse(url="/wallets", status_code=303)
    except ValueError:
        return ValueError("Invalid wallet id", status_code=400)

### Categories Routes
@app.get('/categories')
async def get_categories(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    username = crud.get_user(db, user_id=user_id).fullname
    categories = crud.get_categories(db, user_id=user_id)
    transaction_types = crud.get_transaction_types(db, ie=True)
    return templates.TemplateResponse('categories.html', 
                                      {'request': request,
                                       'username': username,
                                       'categories': categories,
                                       'transaction_types': transaction_types})

@app.post("/categories/create")
async def add_category(request: Request,
                category: Annotated[str, Form()],
                transaction_type_id: Annotated[str, Form()],
                description: Annotated[str, Form()],
                db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    try:
        crud.create_category(db=db, user_id=user_id, transaction_type_id=transaction_type_id, category_name=category, description=description)
        return RedirectResponse(url="/categories", status_code=303)
    except ValueError:
        return ValueError("Invalid category name", status_code=400)

@app.post("/categories/update")
async def update_category(category_id: Annotated[int, Form()],
                    category: Annotated[str, Form()],
                    transaction_type_id: Annotated[str, Form()],
                    description: Annotated[str, Form()],    
                    db: Session = Depends(get_db)):
    try:
        crud.update_category(db=db, category_id=category_id, transaction_type_id=transaction_type_id, category_name=category, description=description)
        return RedirectResponse(url="/categories", status_code=303)
    except ValueError:
        return ValueError("Invalid category id", status_code=400)

### User Routes
@app.get('/login')
def get_login(request: Request):
    return templates.TemplateResponse('login.html', {'request': request, 'error': None})

@app.post('/login')
async def login(request: Request, db: Session = Depends(get_db)):
    form = schemas.LoginForm(request)
    await form.load_data()  # Load form data asynchronously

    user = crud.get_user_by_username(db, username=form.username)
    if not user:
        return templates.TemplateResponse('login.html', {'request': request, 'error': "Invalid username"})

    if not crud.verify_password(db, user, form.password):
        return templates.TemplateResponse('login.html', {'request': request, 'error': "Invalid password"})

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True)
    return response

@app.get('/logout')
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="user_id")
    return response

@app.post('/signup')
async def signup(request: Request, db: Session = Depends(get_db)):
    form = schemas.SignupForm(request)
    await form.load_data()  # Load form data asynchronously

    user = crud.get_user_by_username(db, username=form.username)
    if user:
        return templates.TemplateResponse('login.html', {'request': request, 'error': "Username already exists"})

    user = crud.get_user_by_email(db, email=form.email)
    if user:
        return templates.TemplateResponse('login.html', {'request': request, 'error': "Email already exists"})

    user = crud.create_user(db, user=form)
    
    # New user setup
    with open('preparation/initial_categories.txt', 'r') as category_file:
        initial_categories_txt = category_file.read()
    initial_categories = ast.literal_eval(initial_categories_txt)

    with open('preparation/initial_wallets.txt', 'r') as wallet_file:
        initial_wallets_txt = wallet_file.read()
    initial_wallets = ast.literal_eval(initial_wallets_txt)

    crud.new_user_setup(db, wallet_list=initial_wallets, category_list=initial_categories, user_id=user.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True)
    return response
