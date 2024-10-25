import app.crud as crud
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.io as pio
import plotly.graph_objs as go

colors_map = ["#1d7af3", "#FE5E7B", "#fdaf4b", "#18DFAC", "#6861CE", "#FF79D8", "#53F1F1", "#FFA451"]

### Assets Dashboard
def assets_pie_plot(wallets_df, darkmode):
    ### Plot Assets pie chart
    pie_chart_dataset = wallets_df[wallets_df['current_balance'] > 0]
    if len(pie_chart_dataset) == 0:
        return None
    
    if darkmode=='dark':
        fig = px.pie(pie_chart_dataset, values='current_balance',
                    names='wallet_name', color_discrete_sequence=colors_map,
                    template='plotly_dark',
                    category_orders={'wallet_name': pie_chart_dataset['wallet_name'].tolist()})
        # Update layout to customize dark theme appearance
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',  # Transparent background
            plot_bgcolor='rgba(0,0,0,0)',   # Transparent plot area
            font=dict(color='white'),       # Text color
        )
    else:
        fig = px.pie(pie_chart_dataset, values='current_balance',
                    names='wallet_name', color_discrete_sequence=colors_map,
                    category_orders={'wallet_name': pie_chart_dataset['wallet_name'].tolist()})

    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Percentage: %{percent}<br>Balance: %{value}<extra></extra>",
        hoverinfo='label+percent+value')
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                      height=300)
    pie_chart_html = pio.to_html(fig, full_html=False)

    return pie_chart_html

def cashflow_plot(db, assets_transactions_df, wallets_df, fromdate, todate, wallet_filter, darkmode):
    cashflow_dataset = assets_transactions_df.copy()
    selected_wallet = None

    if fromdate is not None:
        fromdate_dt = pd.to_datetime(fromdate)
        cashflow_dataset = cashflow_dataset[cashflow_dataset['transaction_date'] >= fromdate_dt]
    if todate is not None:
        todate_dt = pd.to_datetime(todate)
        cashflow_dataset = cashflow_dataset[cashflow_dataset['transaction_date'] <= todate_dt]
    if wallet_filter is not None:
        cashflow_dataset = cashflow_dataset[cashflow_dataset['wallet_id'] == wallet_filter]
        selected_wallet = crud.get_wallet_by_id(db, wallet_id=wallet_filter)
        

    # Calculate inflow and outflow
    inflow = cashflow_dataset[cashflow_dataset['transaction_type_id'] != 1] \
        .groupby('transaction_date', as_index=False)['amount'].sum() \
        .rename(columns={'amount': 'inflow'})
    
    outflow = cashflow_dataset[cashflow_dataset['transaction_type_id'] == 1] \
        .groupby('transaction_date', as_index=False)['amount'].sum() \
        .rename(columns={'amount': 'outflow'})

    # Merge inflow and outflow
    cashflow_dataset = pd.merge(left=inflow, right=outflow, on='transaction_date', how='outer').fillna({'inflow': 0, 'outflow': 0})

    # Calculate net amount and cumulative sum
    inital_balance = wallets_df['initial_balance'].sum() if wallet_filter is None else selected_wallet.initial_balance
    cashflow_dataset['amount'] = cashflow_dataset['inflow'] - cashflow_dataset['outflow']
    cashflow_dataset = cashflow_dataset.sort_values(by='transaction_date').reset_index()
    cashflow_dataset.loc[0, 'amount'] = cashflow_dataset.loc[0, 'amount'] + inital_balance
    cashflow_dataset['cumsum'] = cashflow_dataset['amount'].cumsum()

    # Create plot
    template = 'plotly_dark' if darkmode=='dark' else 'plotly_white'
    fig = px.line(
            cashflow_dataset,
            x='transaction_date',
            y='cumsum',
            template=template,
            color_discrete_sequence=colors_map
        )
    fig.update_traces(
        fill='tozeroy',
        line_shape='spline',
        line=dict(color='#18DFAC'),
        hovertemplate="<b>%{x}</b><br>Balance: %{y}<extra></extra>"
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                      height=300)
    
    if darkmode=='dark':
        # Update layout to customize dark theme appearance
        fig.update_layout(
            xaxis_title="",
            yaxis_title="",
            paper_bgcolor='rgba(0,0,0,0)',  # Transparent background
            plot_bgcolor='rgba(0,0,0,0)',   # Transparent plot area
            font=dict(color='white'),       # Text color
            xaxis=dict(
                gridcolor='rgba(255, 255, 255, 0.2)',  # Light grid lines for contrast
                showgrid=True,
                zeroline=False
            ),
            yaxis=dict(
                gridcolor='rgba(255, 255, 255, 0.2)',  # Light grid lines for contrast
                showgrid=True,
                zeroline=False
            )
        )
    
    # Convert the figure to HTML
    cashflow_chart_html = pio.to_html(fig, full_html=False)

    return cashflow_chart_html, selected_wallet

def assets_dashboard(request, db, templates, fromdate=None, todate=None, wallet_filter=None):
    global colors_map
    
    darkmode = request.cookies.get("darkmode")
    user_id = request.cookies.get("user_id")
    user = crud.get_user(db, user_id=user_id)
    username = user.fullname
    currency = user.currency
    assets_wallets = crud.get_wallets(db, user_id=user_id, liability=0)
    wallets_df = pd.DataFrame([wallet.__dict__ for wallet in assets_wallets])
    debt_wallets = crud.get_wallets(db, user_id=user_id, liability=1)
    debt_wallets_df = pd.DataFrame([wallet.__dict__ for wallet in debt_wallets]) if len(debt_wallets) > 0 else None

    all_options = {'wallets': [{'id': wallet.id, 'name': wallet.wallet_name} for wallet in assets_wallets],
                    'debts': [{'id': debt.id, 'name': debt.wallet_name} for debt in debt_wallets]}
    transactions = crud.get_transactions(db, user_id=user_id)

    ### Calculate initial balances
    inital_balance = wallets_df['initial_balance'].sum()
    initial_payables = initial_receivables = payables = receivables = 0
    if len(debt_wallets) > 0:
        initial_payables = wallets_df[(wallets_df['liability'] == 1) & (wallets_df['initial_balance'] < 0)]['initial_balance'].sum()
        initial_receivables = wallets_df[(wallets_df['liability'] == 1) & (wallets_df['initial_balance'] > 0)]['initial_balance'].sum()

    # Handle no transactions case
    if len(transactions) == 0:
        scorecard = {"available_assets": inital_balance,
                    "receivables": initial_receivables,
                    "payables": abs(initial_payables)}
        wallets_df['current_balance'] = wallets_df['initial_balance']
        wallets_df['assets_distribution'] = np.where(wallets_df['initial_balance'] > 0, wallets_df['initial_balance'] / wallets_df['initial_balance'].sum(), 0)
        if debt_wallets_df is not None:
            debt_wallets_df['debts'] = debt_wallets_df['initial_balance']
        
        ### Plot Assets pie chart
        pie_chart_html = assets_pie_plot(wallets_df, darkmode)
        print({'request': request,
            'username': username,
            'scorecard': scorecard,
            'wallets': wallets_df.to_dict('records'),
            'debt_wallets': debt_wallets_df.to_dict('records') if debt_wallets_df is not None else None,
            'all_options': all_options,
            'currency': currency})
        return templates.TemplateResponse("assets_dashboard.html", {'request': request,
                                                                'username': username,
                                                                'scorecard': scorecard,
                                                                'wallets': wallets_df.to_dict('records'),
                                                                'debt_wallets': debt_wallets_df.to_dict('records') if debt_wallets_df is not None else None,
                                                                'assets_pie': pie_chart_html,
                                                                'all_options': all_options,
                                                                'currency': currency})

    transactions_df = pd.DataFrame([transaction.__dict__ for transaction in transactions])
    assets_transactions_df = transactions_df[transactions_df['wallet_id'].isin([wallet.id for wallet in assets_wallets])]
    debts_transactions_df = transactions_df[transactions_df['wallet_id'].isin([debt.id for debt in debt_wallets])]
    
    if len(debt_wallets) > 0:
        ### Calculate Debts balance
        debt_wallets_groupby = debts_transactions_df.groupby('wallet_id', as_index=False)['amount'].sum().rename(columns={'amount': 'debts'})
        debt_wallets_df = debt_wallets_df.merge(debt_wallets_groupby, left_on='id', right_on='wallet_id', how='outer')
        debt_wallets_df = debt_wallets_df[debt_wallets_df['debts'] != 0]

        receivables = debt_wallets_df[debt_wallets_df['debts'] > 0]['debts'].sum()
        payables = debt_wallets_df[debt_wallets_df['debts'] < 0]['debts'].sum()
    
    ### Calculate scorecard values
    positve_df = assets_transactions_df[assets_transactions_df['transaction_type_id'] != 1]
    expense_df = assets_transactions_df[assets_transactions_df['transaction_type_id'] == 1]
    
    
    total_cashin = positve_df['amount'].sum()
    total_cashout = expense_df['amount'].sum()
    scorecard = {"available_assets": inital_balance + total_cashin - total_cashout,
                "receivables": receivables + initial_receivables,
                "payables": abs(payables + initial_payables)}

    ### Calculate Assets distribution
    positive_transactions = positve_df.groupby('wallet_id', as_index=False)['amount'].sum().rename(columns={'amount': 'positve'})
    negative_transactions = expense_df.groupby('wallet_id', as_index=False)['amount'].sum().rename(columns={'amount': 'negative'})

    wallets_df = wallets_df.merge(positive_transactions, left_on='id', right_on='wallet_id', how='outer')
    wallets_df = wallets_df.merge(negative_transactions, left_on='id', right_on='wallet_id', how='outer')

    wallets_df = wallets_df.fillna({'positve': 0, 'negative': 0})
    wallets_df['current_balance'] = wallets_df['initial_balance'] + wallets_df['positve'] - wallets_df['negative']
    wallets_df['assets_distribution'] = np.where(wallets_df['current_balance'] > 0, wallets_df['current_balance'] / wallets_df[wallets_df['current_balance'] > 0]['current_balance'].sum(), 0)
 
    wallets_df = wallets_df.sort_values(by='current_balance', ascending=False)

    ### Plot Assets pie chart
    pie_chart_html = assets_pie_plot(wallets_df, darkmode)

    ### Plot Cashflow
    cashflow_chart_html, selected_wallet = cashflow_plot(db, assets_transactions_df, wallets_df, fromdate, todate, wallet_filter, darkmode)

    return templates.TemplateResponse("assets_dashboard.html", {'request': request,
                                                                'username': username,
                                                                'scorecard': scorecard,
                                                                'wallets': wallets_df.to_dict('records'),
                                                                'selected_wallet': selected_wallet,
                                                                'fromdate': fromdate,
                                                                'todate': todate,
                                                                'debt_wallets': debt_wallets_df.to_dict('records') if debt_wallets_df is not None else None,
                                                                'assets_pie': pie_chart_html,
                                                                'cashflow_chart': cashflow_chart_html,
                                                                'all_options': all_options,
                                                                'currency': currency})

### Income Dashboard
def ie_bar_chart(df, darkmode, type):
    template = 'plotly_dark' if darkmode=='dark' else 'plotly_white'
    fig = px.bar(
            df,
            x='amount',
            y='category_name',
            template=template,
            color_discrete_sequence=colors_map,
            orientation='h',
            text='amount'
        )
    
    barcolor = "#18DFAC" if type == "income" else "#FE5E7B"
    fig.update_traces(
        marker=dict(color=barcolor),
        hovertemplate="<b>%{y}</b><br>%{x}<extra></extra>",
        texttemplate='%{text:,}'  # Format text with thousand separator
    )
    fig.update_layout(xaxis_title="",
                    yaxis_title="",
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=300,
                    yaxis=dict(
                        ticklen=10,  # Length of tick lines
                    )
    )
    
    if darkmode=='dark':
        # Update layout to customize dark theme appearance
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',  # Transparent background
            plot_bgcolor='rgba(0,0,0,0)',   # Transparent plot area
            font=dict(color='white'),       # Text color
            xaxis=dict(
                gridcolor='rgba(255, 255, 255, 0.2)',  # Light grid lines for contrast
                showgrid=True,
                zeroline=False
            )
        )

    # Convert the figure to HTML
    chart_html = pio.to_html(fig, full_html=False)

    return chart_html

def earnings_trend_chart(df, darkmode):
    template = 'plotly_dark' if darkmode == 'dark' else 'plotly_white'
    fig = go.Figure()

    # Add bar trace for earnings
    fig.add_trace(go.Bar(
        x=df['yearmonth'],
        y=df['earnings'],
        name='Earnings',
        marker_color=colors_map[4],
        hovertemplate="<b>%{x}</b><br>Earnings: %{y}<extra></extra>"
    ))

    # Add line trace for income
    fig.add_trace(go.Scatter(
        x=df['yearmonth'],
        y=df['income'],
        mode='lines+markers',
        name='Income',
        line=dict(color=colors_map[3], width=2),
        line_shape='spline',
        marker=dict(size=8)
    ))

    # Add line trace for expense
    fig.add_trace(go.Scatter(
        x=df['yearmonth'],
        y=df['expense'],
        mode='lines+markers',
        name='Expense',
        line=dict(color=colors_map[1], width=2),
        line_shape='spline',
        marker=dict(size=8)
    ))

    # Update layout
    fig.update_layout(
        template=template,  # Set the template here
        margin=dict(l=0, r=0, t=0, b=0),
        height=300,
        xaxis_title="Month",
        yaxis_title="",
        legend=dict(
            orientation="h",  
            yanchor="bottom",
            y=1.02,            # Position above the plot area
            xanchor="center",  # Center the legend
            x=0.5              # Centered horizontally
        )
    )

    if darkmode == 'dark':
        # Update layout to customize dark theme appearance
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',  # Transparent background
            plot_bgcolor='rgba(0,0,0,0)',   # Transparent plot area
            font=dict(color='white'),       # Text color
            xaxis=dict(
                gridcolor='rgba(255, 255, 255, 0.2)',  # Light grid lines for contrast
                showgrid=True,
                zeroline=False
            ),
            yaxis=dict(
                gridcolor='rgba(255, 255, 255, 0.2)',  # Light grid lines for contrast
                showgrid=True,
                zeroline=False
            )
        )

    # Convert the figure to HTML
    earnings_trend_html = pio.to_html(fig, full_html=False)

    return earnings_trend_html

def income_dashboard(request, db, templates, fromdate=None, todate=None, wallet_filter=None):
    user_id = request.cookies.get("user_id")
    user = crud.get_user(db, user_id=user_id)
    username = user.fullname
    currency = user.currency
    darkmode = request.cookies.get("darkmode")
    categories = crud.get_categories(db, user_id=user_id)
    categories_df = pd.DataFrame([category.__dict__ for category in categories])
    wallets = crud.get_wallets(db, user_id=user_id)
    wallets_df = pd.DataFrame([wallet.__dict__ for wallet in wallets])
    transactions_all = crud.get_transactions(db, user_id=user_id, wallet_id=wallet_filter)    
    selected_wallet = wallets_df[wallets_df['id']==wallet_filter].to_dict(orient='records')[0] if wallet_filter else None
    transactions_all_df = pd.DataFrame([transaction.__dict__ for transaction in transactions_all])
    
    # Handle no transaction case
    if transactions_all_df.empty:
        scorecard = {"income": 0,
                 "expense": 0,
                 "earnings": 0,
                 "incomeSparkline": [],
                 "expenseSparkline": []}
        return templates.TemplateResponse("income_dashboard.html", {'request': request,
                                                                'username': username,
                                                                'scorecard': scorecard,
                                                                'wallets': wallets_df[wallets_df['liability'] == 0].to_dict(orient='records'),
                                                                'currency': currency})

    if fromdate is None and todate is None:
        # Set last transaction date as todate and the start of the month as fromdate
        todate = transactions_all[0].transaction_date
        fromdate = todate.replace(day=1)
        todate_str = todate.strftime("%Y-%m-%d")
        fromdate_str = fromdate.strftime("%Y-%m-%d")
    else:
        fromdate_str = fromdate.strftime("%Y-%m-%d")
        todate_str = todate.strftime("%Y-%m-%d")

    transactions_df = transactions_all_df[transactions_all_df['transaction_date'].between(fromdate, todate)]
    income_df = transactions_df[transactions_df['transaction_type_id'] == 2]
    expense_df = transactions_df[transactions_df['transaction_type_id'] == 1]

    ### Calculate scorecard values
    def date_fill(df, mindate=fromdate, maxdate=todate):
        for date in pd.date_range(start=mindate, end=maxdate):
            if date not in df['transaction_date'].values:
                df.loc[len(df.index)] = [date, 0]
        return df
    
    income = income_df['amount'].sum()
    expense = expense_df['amount'].sum()
    earnings = income - expense
    income_by_date = income_df.groupby('transaction_date', as_index=False)['amount'].sum()\
                            .sort_values('transaction_date')
    income_by_date = date_fill(income_by_date).rename(columns={'amount': 'income'})

    expense_by_date = expense_df.groupby('transaction_date', as_index=False)['amount'].sum()\
                            .sort_values('transaction_date')
    expense_by_date = date_fill(expense_by_date).rename(columns={'amount': 'expense'})

    income_statement = pd.merge(left=income_by_date, right=expense_by_date, on='transaction_date', how='outer')\
        .fillna({'income': 0, 'expense': 0})
    income_statement['income_cumsum'] = income_statement['income'].cumsum()
    income_statement['expense_cumsum'] = income_statement['expense'].cumsum()

    scorecard = {"income": income,
                 "expense": expense,
                 "earnings": earnings,
                 "incomeSparkline": income_statement['income_cumsum'].tolist(),
                 "expenseSparkline": income_statement['expense_cumsum'].tolist()}
    
    ### Plot Income chart    
    income_by_category = income_df.groupby('category_id', as_index=False)['amount'].sum().sort_values('amount')
    income_by_category = income_by_category.merge(categories_df, left_on='category_id', right_on='id', how='left')
    income_chart_data = income_by_category[['category_name', 'amount']]
    income_chart_html = ie_bar_chart(income_chart_data, darkmode, 'income')

    ### Plot Expense chart
    expense_by_category = expense_df.groupby('category_id', as_index=False)['amount'].sum().sort_values('amount')
    expense_by_category = expense_by_category.merge(categories_df, left_on='category_id', right_on='id', how='left')
    expense_chart_data = expense_by_category[['category_name', 'amount']]
    expense_chart_html = ie_bar_chart(expense_chart_data, darkmode, 'expense')
    
    ### Plot Cashflow chart
    transactions_6months = transactions_all_df[transactions_all_df['transaction_date'].between(fromdate - relativedelta(months=6), todate)]
    transactions_6months['yearmonth'] = transactions_6months['transaction_date'].dt.strftime('%Y%m')
    income_6months = transactions_6months[transactions_6months['transaction_type_id'] == 2]
    expense_6months = transactions_6months[transactions_6months['transaction_type_id'] == 1]
    income_by_month = income_6months.groupby('yearmonth', as_index=False)['amount'].sum().rename(columns={'amount': 'income'})
    expense_by_month = expense_6months.groupby('yearmonth', as_index=False)['amount'].sum().rename(columns={'amount': 'expense'})
    earnings_by_month = pd.merge(left=income_by_month, right=expense_by_month, on='yearmonth', how='outer').fillna({'income': 0, 'expense': 0})
    earnings_by_month['earnings'] = earnings_by_month['income'] - earnings_by_month['expense']
    earnings_chart_data = earnings_by_month[['yearmonth', 'income', 'expense', 'earnings']]
    earnings_trend_html = earnings_trend_chart(earnings_chart_data, darkmode)

    ### Cashflow table
    transactions_df = pd.merge(transactions_df, wallets_df[['id', 'wallet_name', 'liability']], left_on='wallet_id', right_on='id', how='left')
    transactions_df = pd.merge(transactions_df, categories_df[['id', 'category_name']], left_on='category_id', right_on='id', how='left')
    asset_wallet_cdn = transactions_df['liability'] != 1

    income_cdn = transactions_df['transaction_type_id'] == 2
    debt_collection_cdn = (transactions_df['transaction_type_id'] == 4) & (transactions_df['amount'] > 0)
    positive_df = transactions_df[asset_wallet_cdn & (income_cdn | debt_collection_cdn)]
    positive_df.fillna({'category_name': 'borrow/collect', 'category_id': 0}, inplace=True)
    cashinflow_by_category = positive_df.groupby(['category_name', 'category_id'], as_index=False)['amount'].sum()
    
    expense_cdn = transactions_df['transaction_type_id'] == 1
    debt_payment_cdn = (transactions_df['transaction_type_id'] == 4) & (transactions_df['amount'] < 0)
    negative_df = transactions_df[asset_wallet_cdn & (expense_cdn | debt_payment_cdn)]
    negative_df.fillna({'category_name': 'pay/lend', 'category_id': 0}, inplace=True)
    negative_df['amount'] = negative_df['amount'].abs()
    cashoutflow_by_category = negative_df.groupby(['category_name', 'category_id'], as_index=False)['amount'].sum()
    
    if wallet_filter is not None:
        transfers_cdn = (transactions_df['transaction_type_id'] == 3) & (transactions_df['wallet_id'] == wallet_filter)
        transfer_df = transactions_df[asset_wallet_cdn | transfers_cdn]
        transfer_df['category_name'] = np.where(transfer_df['amount']>0, 'transfer in', 'transfer out')
        transfer_df['category_id'] = np.where(transfer_df['amount']>0, -1, -2)
        transfers_by_category = transfer_df.groupby(['category_name', 'category_id'], as_index=False)['amount'].sum()
        transfer_in = transfers_by_category[transfers_by_category['category_name'] == 'transfer in']
        transfer_out = transfers_by_category[transfers_by_category['category_name'] == 'transfer out']
        transfer_out['amount'] = transfer_out['amount'].abs()
        cashinflow_by_category = pd.concat([cashinflow_by_category, transfer_in], axis=0)
        cashoutflow_by_category = pd.concat([cashoutflow_by_category, transfer_out], axis=0)

    cashinflow_by_category['percentage'] = cashinflow_by_category['amount'] / cashinflow_by_category['amount'].sum()
    cashoutflow_by_category['percentage'] = cashoutflow_by_category['amount'] / cashoutflow_by_category['amount'].sum()

    cash_inflow = {'df': cashinflow_by_category.sort_values('amount', ascending=False).to_dict(orient='records'),
                   'total': cashinflow_by_category['amount'].sum()} if len(cashinflow_by_category) > 0 else None
    cash_outflow = {'df': cashoutflow_by_category.sort_values('amount', ascending=False).to_dict(orient='records'),
                    'total': cashoutflow_by_category['amount'].sum()} if len(cashoutflow_by_category) > 0 else None

    
    return templates.TemplateResponse("income_dashboard.html", {'request': request,
                                                                'username': username,
                                                                'fromdate': fromdate_str,
                                                                'todate': todate_str,
                                                                'selected_wallet': selected_wallet,
                                                                'scorecard': scorecard,
                                                                'wallets': wallets_df[wallets_df['liability'] == 0].to_dict(orient='records'),
                                                                'income_chart': income_chart_html,
                                                                'expense_chart': expense_chart_html,
                                                                'earnings_chart': earnings_trend_html,
                                                                'cash_inflow': cash_inflow,
                                                                'cash_outflow': cash_outflow,
                                                                'currency': currency})