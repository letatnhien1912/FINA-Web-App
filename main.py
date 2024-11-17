from fastapi import FastAPI, Request, Form, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import app.crud as crud, app.models as models, app.schemas as schemas
from app.reports import *
from app.formatting import *
from app.database import SessionLocal, engine
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
    user = crud.get_user(db, user_id=user_id)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    
    if user.is_active == 0:
        response = RedirectResponse(url="/login", status_code=303)
        response.set_cookie(key="user_id", value="", httponly=True)
        return response

    return RedirectResponse(url="/assets_dashboard", status_code=303)

@app.get("/profile", response_class=HTMLResponse)
async def read_profile(request: Request, db: Session = Depends(get_db), error_message=None):
    user_id = request.cookies.get("user_id")
    user = crud.get_user(db, user_id=user_id)
    return templates.TemplateResponse("profile.html", {"request": request,
                                                       "username": user.fullname,
                                                       "user": user,
                                                       "currencies": currencies.keys(),
                                                       'error_message': error_message})

@app.post("/users/update", response_class=HTMLResponse)
def update_user(request: Request,
                username: Annotated[str, Form()] = None,
                fullname: Annotated[str, Form()] = None,
                email: Annotated[str, Form()] = None,
                currency: Annotated[str, Form()] = None,
                db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    error_message = 'None'

    try:
        crud.update_user(db=db,
                        user_id=user_id,
                        username=username,
                        fullname=fullname,
                        email=email,
                        currency=currency)
    except HTTPException as e:
        error_message = e.detail
        return RedirectResponse(url="/profile?error_message=" + error_message + "", status_code=303)

    return RedirectResponse(url="/profile", status_code=303)

@app.post("/users/inactive")
def delete_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    db_user = crud.inactive_user(db=db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return RedirectResponse('/', status_code=303)

@app.post("/users/delete")
def delete_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    db_user = crud.delete_user(db=db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return RedirectResponse('/', status_code=303)

templates.env.filters['format_number'] = format_number
templates.env.filters['format_percentage'] = format_percentage
templates.env.filters['format_date'] = format_date
templates.env.filters['format_money'] = lambda x, currency='VND': format_money(x, currency)

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
    transaction_types = crud.get_transaction_types(db)
    transactions = crud.get_transactions(db, user_id=user_id,
                                         wallet_id=wallet_id if wallet_id else None,
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
        error = "No records found" +  "<br>" + error if error is not None else "No records found"
        return templates.TemplateResponse('transactions.html', 
                                      {'request': request,
                                       'username': username,
                                       'transactions': None,
                                       'options': None,
                                       'all_options': all_options,
                                       'pagination': None,
                                       'error': error,
                                       'currency': user.currency})
    
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
                                       'error': error,
                                       'currency': user.currency})

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
    try:
        crud.create_transaction(db=db,
                                user_id=user_id,
                                wallet_id=wallet_id,
                                category_id=category_id,
                                transaction_type_id=transaction_type_id,
                                amount=amount,
                                transaction_date=selected_date,
                                description=description)
        return RedirectResponse(url='/transactions', status_code=303)
    except HTTPException as e:
        return RedirectResponse(url=f'/transactions?error={e.detail}', status_code=303)

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

        if wallet_to_first is None:
            crud.create_wallet(db=db, user_id=user_id, wallet_name=wallet_to, liability=1)
            wallet_to_first = crud.get_wallet_by_name(db=db, user_id=user_id, wallet_name=wallet_to)
        
    if transaction_type_id==3:
        wallet_to_first = crud.get_wallet_by_id(db=db, wallet_id=int(wallet_to))

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

    return RedirectResponse(url='/transactions', status_code=303)

@app.post("/transactions/update")
async def update_transaction(request: Request,
                    transaction_id: Annotated[int, Form()],
                    selected_date: Annotated[str, Form()],
                    selected_type: Annotated[str, Form()],
                    wallet: Annotated[str, Form()],
                    amount: Annotated[float, Form()],
                    description: Annotated[Optional[str], Form()] = None,
                    category: Annotated[Optional[str], Form()] = None,
                    db: Session = Depends(get_db)):
    selected_date = datetime.fromisoformat(selected_date).date()
    wallet_id = int(wallet)
    transaction_type_id = int(selected_type)
    category_id = int(category) if category else None

    try:
        crud.update_transaction(db = db,
                                transaction_id = transaction_id,
                                wallet_id = wallet_id,
                                category_id = category_id,
                                transaction_type_id = transaction_type_id,
                                amount = amount,
                                transaction_date = selected_date,
                                description = description)

        return RedirectResponse(url='/transactions', status_code=303)
    except ValueError as e:
        raise e

@app.post("/transactions/delete")
async def delete_transaction(request: Request, db: Session = Depends(get_db)):
    # Perform the deletion
    data = await request.json()
    transaction_id = data.get("transaction_id")
    crud.delete_transaction(db=db, transaction_id=transaction_id)

    # Get the current URL from the 'next' query parameter, default to "/"
    current_url = request.query_params.get("next", "/")
    response = RedirectResponse(url=current_url, status_code=303)
    return response

### Wallets Routes
@app.get('/wallets')
async def get_wallets(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    user = crud.get_user(db, user_id=user_id)
    username = user.fullname
    wallets = crud.get_wallets(db, user_id=user_id, liability=0)
    debts = crud.get_wallets(db, user_id=user_id, liability=1)
    return templates.TemplateResponse('wallets.html', 
                                      {'request': request,
                                       'username': username,
                                       'wallets': wallets,
                                       'debts': debts,
                                       'currency': user.currency})

@app.post("/wallets/create")
async def add_wallet(request: Request,
                wallet: Annotated[str, Form()],
                liability: Annotated[int, Form()],
                initial_balance: Annotated[float, Form()],
               description: Annotated[str, Form()],
               db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    try:
        crud.create_wallet(db=db,
                        user_id=user_id,
                        wallet_name=wallet,
                        liability=liability,
                        initial_balance=initial_balance,
                        description=description)
        return RedirectResponse(url="/wallets", status_code=303)
    except ValueError:
        return ValueError("Invalid wallet name", status_code=400)

@app.post("/wallets/update")
async def update_wallet(request: Request,
                        wallet_id: Annotated[int, Form()],
                        wallet: Annotated[str, Form()],
                        initial_balance: Annotated[float, Form()],
                        description: Annotated[str, Form()],
                        db: Session = Depends(get_db)):
    try:
        crud.update_wallet(db=db,
                           wallet_id=wallet_id,
                           wallet_name=wallet,
                           initial_balance=initial_balance,
                           description=description)
        return RedirectResponse(url='/wallets', status_code=303)
    except ValueError:
        return ValueError("Invalid wallet id", status_code=400)

class deleteWalletRequest(BaseModel):
    wallet_id: int
@app.post("/wallets/delete")
async def delete_wallet(request: deleteWalletRequest,
                  db: Session = Depends(get_db)):
    
    try:
        crud.delete_wallet(db=db, wallet_id=request.wallet_id)
        current_url = request.query_params.get("next", "/")
        response = RedirectResponse(url=current_url, status_code=303)
        return response
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
        return RedirectResponse(url='/categories', status_code=303)
    except ValueError:
        return ValueError("Invalid category name", status_code=400)

@app.post("/categories/update")
async def update_category(request: Request,
                        category_id: Annotated[int, Form()],
                        category: Annotated[str, Form()],
                        transaction_type_id: Annotated[str, Form()],
                        description: Annotated[str, Form()],    
                        db: Session = Depends(get_db)):
    try:
        crud.update_category(db=db, category_id=category_id, transaction_type_id=transaction_type_id, category_name=category, description=description)
        return RedirectResponse(url='/categories', status_code=303)
    except ValueError:
        return ValueError("Invalid category id", status_code=400)

### User Routes
@app.get('/login')
def get_login(request: Request, error=None):
    return templates.TemplateResponse('login.html', {'request': request,
                                                     'error': None,
                                                     'currencies': currencies.keys(),
                                                     'error': error})

@app.post('/login')
async def login(request: Request, db: Session = Depends(get_db)):
    form = schemas.LoginForm(request)
    await form.load_data()  # Load form data asynchronously

    user = crud.get_user_by_username(db, username=form.username)
    if not user:
        return RedirectResponse(url="/login?error=Invalid+username", status_code=303)
    
    if user.is_active == 0:
        return RedirectResponse(url="/login?error=Your+account+is+inactive.+Contact+Nhien+Le+to+reactivate+your+account.", status_code=303)

    if not crud.verify_password(db, user, form.password):
        return RedirectResponse(url="/login?error=Invalid+password", status_code=303)

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True)
    response.set_cookie(key='darkmode', value=True, httponly=True)
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

    # Check if user exists
    user = crud.get_user_by_username(db, username=form.username)
    if user:
        return RedirectResponse(url="/login?error=Username+already+exists", status_code=303)

    # Check if email exists
    user = crud.get_user_by_email(db, email=form.email)
    if user:
        return RedirectResponse(url="/login?error=Email+already+exists", status_code=303)

    # Check if currency valid
    if form.currency not in currencies.keys():
        return RedirectResponse(url="/login?error=Invalid+currency", status_code=303)

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

### Dashboard routes
@app.get("/theme")
async def get_theme(request: Request, darkmode: str = None):
    print(darkmode)
    if darkmode is None:
        darkmode = 'light'

    # Get the current URL
    current_url = request.query_params.get("next", "/")
    # Set the cookie for dark mode
    response = RedirectResponse(url=current_url, status_code=303)
    response.set_cookie(key="darkmode", value=darkmode, httponly=True)
    return response
    
@app.get("/assets_dashboard")
async def get_assets_dashboard(request: Request,
                               db: Session = Depends(get_db),
                               fromdate: str = None,
                               todate: str = None,
                               wallet: int = None):
    fromdate = fromdate if fromdate != '' else None
    todate = todate if todate != '' else None
    return assets_dashboard(request, db, templates, fromdate=fromdate, todate=todate, wallet_filter=wallet)

@app.get("/income_dashboard")
async def get_income_dashboard(request: Request,
                               db: Session = Depends(get_db),
                               fromdate: str = None,
                               todate: str = None,
                               wallet: int = None):
    fromdate = datetime.fromisoformat(fromdate) if fromdate else None
    todate = datetime.fromisoformat(todate) if todate else None
    return income_dashboard(request, db, templates, fromdate, todate, wallet)