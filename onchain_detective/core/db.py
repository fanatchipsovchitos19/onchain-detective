"""
Слой базы данных (SQLite + SQLAlchemy) для хранения кошельков и связей.
"""

from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, ForeignKey, Table
from sqlalchemy.orm import DeclarativeBase, Session, relationship
from datetime import datetime
from pathlib import Path
from ..config import settings


class Base(DeclarativeBase):
    pass


# Таблица связи "многие ко многим" между кошельками
wallet_links = Table(
    "wallet_links",
    Base.metadata,
    Column("wallet_id", Integer, ForeignKey("wallets.id"), primary_key=True),
    Column("linked_wallet_id", Integer, ForeignKey("wallets.id"), primary_key=True),
    Column("weight", Float, default=1.0),  # сила связи
    Column("common_tx_count", Integer, default=0),  # количество общих транзакций
)


class Wallet(Base):
    """Модель кошелька."""
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(42), unique=True, index=True, nullable=False)
    balance_native = Column(Float, default=0.0)
    balance_usd = Column(Float, default=0.0)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    total_tx_count = Column(Integer, default=0)
    is_contract = Column(Integer, default=0)
    cluster_id = Column(Integer, default=None, nullable=True)  # ID кластера (если сгруппирован)

    # Связи с другими кошельками
    linked_wallets = relationship(
        "Wallet",
        secondary=wallet_links,
        primaryjoin="Wallet.id == wallet_links.c.wallet_id",
        secondaryjoin="Wallet.id == wallet_links.c.linked_wallet_id",
        backref="linked_from",
    )

    def __repr__(self):
        return f"<Wallet {self.address[:10]}...>"


# Глобальный движок (синглтон)
_engine = None


def get_engine():
    """Получить или создать движок БД."""
    global _engine
    if _engine is None:
        db_path = settings.DATA_DIR / "onchain_detective.db"
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    """Создать новую сессию."""
    return Session(get_engine())