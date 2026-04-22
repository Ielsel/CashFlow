import customtkinter
from decimal import Decimal, getcontext
from ..tools import cash_format, transaction_deposit_verify
from ..services import balance_deposit
import pandas as pd

class balance_frame(customtkinter.CTkFrame):
    def __init__(self, master, app,**kwargs):
        super().__init__(master, **kwargs)

        self.app = app

        # Título
        self.title_menu = customtkinter.CTkLabel(self, text="Menu de Saldo")
        self.title_menu.grid(row=0, column=0, padx=20, pady=20, columnspan=2)

        # Saldo disponível
        self.available_balance = customtkinter.CTkLabel(self, text=f"Saldo disponível: R${str(cash_format(self.app.balance)).replace(".", ",")}")
        self.available_balance.grid(row=1, column=0, padx=20, pady=20, columnspan=2)

        # Extrato
        self.btn_account_statement = customtkinter.CTkButton(self, text="Extrato", command=self.display_account_statement)
        self.btn_account_statement.grid(row=2, column=0, columnspan=2, padx=20, pady=10)

        # Depósito (entry + botão na mesma linha)
        self.info_label = customtkinter.CTkLabel(self, text="")
        self.info_label.grid(row=7, column=0, columnspan=2, padx=20, pady=10)
        self.entry_amount = customtkinter.CTkEntry(self, placeholder_text="Valor R$")
        self.entry_amount.grid(row=3, column=0, padx=20, pady=10)

        self.btn_deposit = customtkinter.CTkButton(self, text="Depositar", command=self.display_deposit)
        self.btn_deposit.grid(row=3, column=1, padx=20, pady=10)

        # Saque (entry + botão na mesma linha)
        self.entry_withdraw = customtkinter.CTkEntry(self, placeholder_text="Valor R$")
        self.entry_withdraw.grid(row=4, column=0, padx=20, pady=10)

        self.btn_withdraw = customtkinter.CTkButton(self, text="Sacar")
        self.btn_withdraw.grid(row=4, column=1, padx=20, pady=10)

        # Atualizar saldo
        self.btn_update = customtkinter.CTkButton(self, text="Atualizar saldo")
        self.entry_update = customtkinter.CTkEntry(self, placeholder_text="Valor R$")
        self.entry_update.grid(row=5, column=0, padx=20, pady=10)
        self.btn_update.grid(row=5, column=1, columnspan=2, padx=20, pady=10)

        # Voltar
        self.btn_exit = customtkinter.CTkButton(self, text="Voltar", command=self.app.show_main)
        self.btn_exit.grid(row=6, column=0, columnspan=2, padx=20, pady=20)

    #===========
    # Funções
    #===========
    def update_balance_label(self):
        self.available_balance.configure(text=f"Saldo disponível: R${str(cash_format(self.app.balance)).replace(".", ",")}")
        self.info_label.configure(text="")

    def display_deposit(self):
        amount_text = self.entry_amount.get().replace(",", ".")
        amount = Decimal(amount_text)
        if transaction_deposit_verify(amount):
            self.app.balance, self.app.account_statement, _ = balance_deposit(self.app.balance, self.app.account_statement, amount)
            self.update_balance_label()
        else:
            self.info_label.configure(text="Valor inválido!")

    def display_account_statement(self):
        print("\n--EXTRATO--")

        if self.app.account_statement == []:
            print("\nSem extrato disponível!\n")
        else:
            account_statement_dataframe = pd.DataFrame(data = self.app.account_statement)
            print(f"\n{account_statement_dataframe}\n")

        '''
        if balance_option == 1:
                print("\n--EXTRATO--")

                if account_statement == []:
                    print("\nSem extrato disponível!\n")
                else:
                    account_statement_dataframe = pd.DataFrame(data = account_statement)
                    print(f"\n{account_statement_dataframe}\n")
        '''