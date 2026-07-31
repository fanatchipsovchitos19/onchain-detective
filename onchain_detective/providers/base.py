from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Transaction:
    """Стандартизированная модель транзакции (независимо от источника)."""
    hash: str
    block_number: int
    timestamp: datetime
    from_address: str
    to_address: str
    value: float
    raw: dict = field(default_factory=dict, repr=False)
    value_usd: Optional[float] = None
    gas_used: Optional[int] = None
    gas_price: Optional[float] = None
    is_error: bool = False
    input_data: str = ""


@dataclass
class TokenTransfer:
    """Модель трансфера токенов (ERC-20 / ERC-721)."""
    token_address: str
    from_address: str
    to_address: str
    value: float
    transaction_hash: str
    block_number: int
    timestamp: datetime
    token_name: Optional[str] = None
    token_symbol: Optional[str] = None


@dataclass
class WalletInfo:
    """Информация о кошельке."""
    address: str
    balance_native: float
    balance_usd: Optional[float] = None
    first_tx_date: Optional[datetime] = None
    last_tx_date: Optional[datetime] = None
    total_tx_count: int = 0
    is_contract: bool = False


class BaseProvider(ABC):
    """Абстрактный класс провайдера данных."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.name = self.__class__.__name__

    @abstractmethod
    def get_transactions(self, address: str, start_block: int = 0, end_block: int = 99999999) -> list[Transaction]:
        ...

    @abstractmethod
    def get_token_transfers(self, address: str, token_address: str = None,
                            start_block: int = 0, end_block: int = 99999999) -> list[TokenTransfer]:
        ...

    @abstractmethod
    def get_wallet_info(self, address: str) -> WalletInfo:
        ...

    @abstractmethod
    def get_contract_creator(self, contract_address: str) -> Optional[str]:
        ...

    def __repr__(self):
        return f"<{self.name}>"