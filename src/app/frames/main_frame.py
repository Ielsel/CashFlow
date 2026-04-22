import customtkinter
from ..tools import *

class main_frame(customtkinter.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)

        self.app = app

        self.available_balance = customtkinter.CTkLabel(self, text=f"Saldo disponível: R${cash_format(app.balance)}") 
        self.available_balance.pack(padx=10, pady=10)

        self.btn_balance_menu = customtkinter.CTkButton(self, text="Menu de saldo", command=self.app.show_balance)
        self.btn_balance_menu.pack(padx=10, pady=10)

        self.btn_reserve_menu = customtkinter.CTkButton(self, text="Menu de reservas", command=self.app.show_reserve)
        self.btn_reserve_menu.pack(padx=10, pady=10)
        
