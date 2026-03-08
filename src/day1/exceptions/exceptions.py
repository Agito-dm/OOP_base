"""
Пользовательские исключения для банковских счетов (Day1).
"""


class AccountFrozenError(Exception):
    """Операция запрещена: счёт заморожен."""


class AccountClosedError(Exception):
    """Операция запрещена: счёт закрыт."""


class InvalidOperationError(Exception):
    """Некорректная операция (например, неверная сумма пополнения/снятия)."""


class InsufficientFundsError(Exception):
    """Недостаточно средств для выполнения операции."""
