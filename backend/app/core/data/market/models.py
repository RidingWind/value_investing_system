"""
日线行情数据模型
用于 SQLAlchemy 映射与数据库操作
"""
from sqlalchemy import Column, Integer, String, Date, Numeric, DateTime, UniqueConstraint, Index, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class DailyQuote(Base):
    """日线行情表（复权数据）"""
    __tablename__ = "daily_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, comment="股票代码（去除交易所后缀）")
    trade_date = Column(Date, nullable=False, comment="交易日期")
    open = Column(Numeric(15, 4), comment="开盘价（前复权）")
    high = Column(Numeric(15, 4), comment="最高价（前复权）")
    low = Column(Numeric(15, 4), comment="最低价（前复权）")
    close = Column(Numeric(15, 4), comment="收盘价（前复权）")
    volume = Column(Numeric(20, 2), comment="成交量（股）")
    amount = Column(Numeric(20, 2), comment="成交额（元）")
    adj_factor = Column(Numeric(15, 6), default=1.0, comment="后复权因子，用于从后复权价格反向推导真实价格")
    source = Column(String(20), default="akshare", comment="数据来源")
    created_at = Column(DateTime, default=func.now(), comment="记录创建时间")

    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", name="uq_daily_quote_symbol_date"),
        Index("idx_daily_quotes_symbol", "symbol"),
        Index("idx_daily_quotes_date", "trade_date"),
    )