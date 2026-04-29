import customtkinter as ctk
from decimal import Decimal
from ..tools import cash_format, transaction_deposit_verify, transaction_verify
from ..services import balance_deposit, balance_withdraw, balance_update

# todo: Melhorar a aparência geral do código usando o claude.ai

class balance_frame(ctk.CTkFrame):
    def __init__(self, master, app,**kwargs):
        super().__init__(master, **kwargs)

        self.app = app

        # Título
        self.title_menu = ctk.CTkLabel(self, text="Menu de Saldo")
        self.title_menu.grid(row=0, column=0, padx=20, pady=20, columnspan=2)

        # Saldo disponível
        self.available_balance = ctk.CTkLabel(self, text=f"Saldo disponível: R${str(cash_format(self.app.balance)).replace(".", ",")}")
        self.available_balance.grid(row=1, column=0, padx=20, pady=20, columnspan=2)

        # Extrato
        self.btn_account_statement = ctk.CTkButton(self, text="Extrato", command=self.app.show_account_statement)
        self.btn_account_statement.grid(row=2, column=0, columnspan=2, padx=20, pady=10)

        # Depósito (entry + botão na mesma linha)
        self.info_label = ctk.CTkLabel(self, text="")
        self.info_label.grid(row=7, column=0, columnspan=2, padx=20, pady=10)
        self.entry_deposit = ctk.CTkEntry(self, placeholder_text="Valor R$")
        self.entry_deposit.grid(row=3, column=0, padx=20, pady=10)

        self.btn_deposit = ctk.CTkButton(self, text="Depositar", command=self.display_deposit)
        self.btn_deposit.grid(row=3, column=1, padx=20, pady=10)

        # Saque (entry + botão na mesma linha)
        self.entry_withdraw = ctk.CTkEntry(self, placeholder_text="Valor R$")
        self.entry_withdraw.grid(row=4, column=0, padx=20, pady=10)
        self.btn_withdraw = ctk.CTkButton(self, text="Sacar", command=self.display_withdraw)
        self.btn_withdraw.grid(row=4, column=1, padx=20, pady=10)

        # Atualizar saldo
        self.btn_update = ctk.CTkButton(self, text="Atualizar saldo", command=self.confirm_update_balance)
        self.entry_update = ctk.CTkEntry(self, placeholder_text="Valor R$")
        self.entry_update.grid(row=5, column=0, padx=20, pady=10)
        self.btn_update.grid(row=5, column=1, columnspan=2, padx=20, pady=10)

        # Voltar pro main menu
        self.btn_exit = ctk.CTkButton(self, text="Voltar", command=self.app.show_main)
        self.btn_exit.grid(row=6, column=0, columnspan=2, padx=20, pady=20)

    #===================
    # Atualizar o frame
    #===================
    def update_balance_frame(self):
        self.available_balance.configure(text=f"Saldo disponível: R${str(cash_format(self.app.balance)).replace(".", ",")}")
        self.info_label.configure(text="")
    
    #====================
    # Mostrar o depósito
    #====================
    def display_deposit(self):
        amount_text = self.entry_deposit.get().replace(",", ".")
        amount = Decimal(amount_text)
        if transaction_deposit_verify(amount):
            self.app.balance, self.app.account_statement, _ = balance_deposit(self.app.balance, self.app.account_statement, amount)
            self.update_balance_frame()
        else:
            self.info_label.configure(text="Valor inválido!")

    
    #====================
    # Mostrar o Saque
    #====================
    def display_withdraw(self):
        amount_text = self.entry_withdraw.get().replace(",", ".")
        amount = Decimal(amount_text)
        if transaction_verify(self.app.balance, amount):
            self.app.balance, self.app.account_statement, _ = balance_withdraw(self.app.balance, self.app.account_statement, amount)
            self.update_balance_frame()
        else:
            self.info_label.configure(text="Valor inválido!")

    #===============================================
    # Pop-up de confirmação da atualização do saldo
    #===============================================
    def confirm_update_balance(self):
        self.confirm_window = ctk.CTkToplevel(self)
        self.confirm_window.title("Confirmação")

        self.confirm_window.geometry("320x150")
        self.confirm_window.resizable(False, False)
        self.confirm_window.grab_set()

        label = ctk.CTkLabel(self.confirm_window, text="Tem certeza que deseja atualizar o saldo?")
        label.grid(row=0, column=0, columnspan=2, padx=20, pady=20)

        btn_confirm = ctk.CTkButton(self.confirm_window, text="Confirmar", command=self.display_update)
        btn_confirm.grid(row=1, column=0, padx=10, pady=10)

        btn_cancel = ctk.CTkButton(self.confirm_window, text="Cancelar", command=self.confirm_window.destroy)
        btn_cancel.grid(row=1, column=1, padx=10, pady=10)

        self.confirm_window.update_idletasks()
    
    #======================
    # Atualização de saldo
    #======================
    def display_update(self):
        amount_text = self.entry_update.get().replace(",", ".")
        amount = Decimal(amount_text)
        
        self.app.balance, self.app.account_statement, _ = balance_update(self.app.balance, self.app.account_statement, amount)
        self.update_balance_frame()

        self.confirm_window.destroy()