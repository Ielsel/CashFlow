import customtkinter
from ..tools import *

class reserve_frame(customtkinter.CTkFrame):
    def __init__(self, master, app,**kwargs):
        super().__init__(master, **kwargs)

        self.app = app

        # Elementos da página

        self.title_menu = customtkinter.CTkLabel(self, text="Menu de Reservas")
        self.title_menu.pack(padx=10, pady=10)

        self.available_balance = customtkinter.CTkLabel(self, text=f"Saldo disponível: R${cash_format(app.balance)}") 
        self.available_balance.pack(padx=10, pady=10)
        
        self.btn_account_statement = customtkinter.CTkButton(self, text="Ver reservas")
        self.btn_account_statement.pack(padx=10, pady=10)

        self.btn_deposit = customtkinter.CTkButton(self, text="Criar reserva")
        self.btn_deposit.pack(padx=10, pady=10)

        self.btn_withdraw = customtkinter.CTkButton(self, text="Alterar reserva")
        self.btn_withdraw.pack(padx=10, pady=10)

        self.btn_update = customtkinter.CTkButton(self, text="Excluir reserva")
        self.btn_update.pack(padx=10, pady=10)

        self.btn_exit = customtkinter.CTkButton(self, text="Voltar", command=self.app.show_main)
        self.btn_exit.pack(padx=10, pady=10)
