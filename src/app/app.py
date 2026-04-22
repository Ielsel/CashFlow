import customtkinter
import pandas as pd
from .tools import *
from decimal import Decimal, getcontext
from src.app.frames.main_frame import main_frame
from src.app.frames.balance_frame import balance_frame
from src.app.frames.reserve_frame import reserve_frame

getcontext().prec = 28

#===========================================
# Classe principal do app, gestor de frames
#===========================================
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.balance = Decimal(0)
        self.reserve = {}
        self.account_statement = []

        self.geometry("350x450") # tamanho da janela

        # Cria os frames
        self.main_frame = main_frame(self, self)
        self.balance_frame = balance_frame(self, self)
        self.reserve_frame = reserve_frame(self, self)

        self.show_main() # Mostra o frame do menu principal

    def show_main(self):
        '''
            Minimiza todos os frames e mostra o menu principal
            fill: preenche todo o espaço disponível x/y/both
            expand: permite que os elementos creçam junto com a janela
        '''
        self.balance_frame.pack_forget()
        self.reserve_frame.pack_forget()
        self.main_frame.pack(fill="both", expand=True)

    def show_balance(self):
        '''
            Minimiza o menu principal e mostra o menu de saldo
        '''
        self.main_frame.pack_forget()
        self.balance_frame.pack(fill="both", expand=True) 

    def show_reserve(self):
        '''
            Minimiza o menu principal e mostra o menu de reserva
        '''
        self.main_frame.pack_forget()
        self.reserve_frame.pack(fill="both", expand=True)

app = App()
app.mainloop() # inicia a janela
