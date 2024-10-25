from datetime import date, datetime

currencies = {
    "VND": {'symbol': "₫", 'format': "{:,.0f}", 'symbol_on_left': False},
    "USD": {'symbol': "$", 'format': "{:,.2f}", 'symbol_on_left': True},
    "EUR": {'symbol': "€", 'format': "{:,.2f}", 'symbol_on_left': True},
    "JPY": {'symbol': "¥", 'format': "{:,.0f}", 'symbol_on_left': False},
    "GBP": {'symbol': "£", 'format': "{:,.2f}", 'symbol_on_left': True},
    "AUD": {'symbol': "$", 'format': "{:,.2f}", 'symbol_on_left': True},
    "KRW": {'symbol': "₩", 'format': "{:,.0f}", 'symbol_on_left': False},
    "THB": {'symbol': "฿", 'format': "{:,.2f}", 'symbol_on_left': True},
}

# Custom filter
def format_number(value: int) -> str:
    return "{:,}".format(value)
def format_percentage(value: float) -> str:
    return "{:.2%}".format(value)
def format_date(value: datetime) -> str:
    return value.strftime("%d/%m/%Y")
def format_money(value: float, currency: str) -> str:
    c_info = currencies[currency]
    if c_info['symbol_on_left']:
        if value < 0:
            return '-' + c_info['symbol'] + c_info['format'].format(abs(value))
        return c_info['symbol'] + c_info['format'].format(value)
    else:
        return c_info['format'].format(value) + ' ' + c_info['symbol']
    
