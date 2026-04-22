from decimal import Decimal, ROUND_HALF_UP
import datetime

#====================================
# Verifica a validade das transações
#====================================
def transaction_verify(balance, amount):
    if balance < amount or amount < 0:
        return False
    else:
        return True
    
#====================================
# Verifica a validade das transações
#====================================
def transaction_deposit_verify(amount):
    if amount <= 0:
        return False
    else:
        return True

#==============
# Formata data
#==============
def date_format():
    return datetime.datetime.now().strftime("%d/%m/%y")

#================================
# Formata os valores pro usuário
#================================
def cash_format(cash_value):
    return cash_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
