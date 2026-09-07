"""
Pacote sheets: integração com o Google Sheets do gestor financeiro.

Reexporta SheetsManager para que o resto do projeto (ex: pipeline.py)
continue fazendo só:

    from sheets import SheetsManager
"""

from .sheets_manager import SheetsManager

__all__ = ["SheetsManager"]
