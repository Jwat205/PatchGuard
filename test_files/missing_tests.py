def calculate_compound_interest(principal, rate, periods):
    return principal * ((1 + rate) ** periods)

def calculate_tax(income, brackets):
    tax = 0
    remaining = income
    for bracket in brackets:
        if remaining <= 0:
            break
        taxable = min(remaining, bracket["limit"])
        tax += taxable * bracket["rate"]
        remaining -= taxable
    return tax

def calculate_portfolio_value(holdings, prices):
    return sum(h["shares"] * prices[h["symbol"]] for h in holdings)
