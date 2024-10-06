from datetime import date, datetime

# Custom filter
def format_number(value: int) -> str:
    return "{:,}".format(value)
def format_percentage(value: float) -> str:
    return "{:.2%}".format(value)
def format_date(value: datetime) -> str:
    return value.strftime("%d/%m/%Y")
def format_money(value: float) -> str:
    return "{:,} ₫".format(int(value))