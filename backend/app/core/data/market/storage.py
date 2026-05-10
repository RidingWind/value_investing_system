import logging
from datetime import date, datetime
from typing import Optional
import pandas as pd
from sqlalchemy import create_engine, event, func
from sqlalchemy.orm import sessionmaker
#如果使用pgsql,将sqlit_insert替换成pg_insert
from sqlalchemy import text
from app.core.data.market.models import Base, DailyQuote
logger = logging.getLogger(__name__)

class DataStorage:
    """持久化行情数据到 PostgreSQL"""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url,
            connect_args={'timeout': 30},  # 遇到锁时等待30秒
            echo=False
        )
        # 启用WAL模式，允许读写并发
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        # self._create_tables()

    def get_summary(self) -> dict:
        session = self.Session()
        try:
            from sqlalchemy import func
            result = session.query(
                func.min(DailyQuote.trade_date),
                func.max(DailyQuote.trade_date),
                func.count(DailyQuote.id)
            ).first()
            start, end, count = result
            symbol_count = session.query(func.count(func.distinct(DailyQuote.symbol))).scalar()
            return {
                "total_records": count,
                "start_date": start,
                "end_date": end,
                "symbol_count": symbol_count or 0
            }
        finally:
            session.close()

    def get_symbol_range(self, symbol: str) -> dict:
        session = self.Session()
        try:
            from sqlalchemy import func
            result = session.query(
                func.min(DailyQuote.trade_date),
                func.max(DailyQuote.trade_date),
                func.count(DailyQuote.id)
            ).filter(DailyQuote.symbol == symbol).first()
            start, end, count = result
            if count == 0:
                return None
            return {
                "symbol": symbol,
                "start_date": start,
                "end_date": end,
                "record_count": count
            }
        finally:
            session.close()

    def save_batch(self, df: pd.DataFrame, source: str = "akshare") -> int:
        """批量存储日线数据（使用原生 upsert 避免参数问题）"""
        if df.empty:
            return 0

        session = self.Session()
        try:
            # 原生 upsert 语句（手动控制所有字段）
            sql = """
                  INSERT INTO daily_quotes (symbol, trade_date, open, high, low, close, volume, amount, adj_factor, \
                                            source, created_at)
                  VALUES (:symbol, :trade_date, :open, :high, :low, :close, :volume, :amount, :adj_factor, :source, \
                          :created_at) ON CONFLICT (symbol, trade_date) DO NOTHING \
                  """
            now = datetime.now(datatime.UTC)
            count = 0
            for _, row in df.iterrows():
                params = {
                    'symbol': str(row['symbol']),
                    'trade_date': row['trade_date'].to_pydatetime().date() if hasattr(row['trade_date'],
                                                                                      'to_pydatetime') else row[
                        'trade_date'],
                    'open': float(row['open']) if not pd.isna(row['open']) else None,
                    'high': float(row['high']) if not pd.isna(row['high']) else None,
                    'low': float(row['low']) if not pd.isna(row['low']) else None,
                    'close': float(row['close']) if not pd.isna(row['close']) else None,
                    'volume': float(row['volume']) if not pd.isna(row['volume']) else None,
                    'amount': float(row['amount']) if not pd.isna(row['amount']) else None,
                    'adj_factor': float(row.get('adj_factor', 1.0)),
                    'source': row.get('source', 'akshare'),
                    'created_at': now
                }
                session.execute(text(sql), params)
                count += 1
            session.commit()
            logger.info(f"成功插入 {count} 条行情数据")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"存储行情数据失败: {e}")
            raise
        finally:
            session.close()

    def get_last_trade_date(self) -> Optional[date]:
        """获取数据库中最新的交易日期"""
        session = self.Session()
        try:
            result = session.execute(text("SELECT MAX(trade_date) FROM daily_quotes"))
            row = result.fetchone()
            return row[0] if row[0] else None
        finally:
            session.close()

    def symbol_has_data(self, symbol: str, trade_date: date) -> bool:
        """检查某只股票在某个日期是否已有数据"""
        session = self.Session()
        try:
            result = session.execute(
                text("SELECT COUNT(*) FROM daily_quotes WHERE symbol = :symbol AND trade_date = :date"),
                {"symbol": symbol, "date": trade_date}
            )
            count = result.scalar()
            return count > 0
        finally:
            session.close()

    from datetime import date, datetime, timedelta
    from typing import Optional, List
    import pandas as pd
    from sqlalchemy import func

    def get_daily_data(self, symbol: str, start_date: date = None, end_date: date = None, freq: str = "daily") -> dict:
        session = self.Session()
        try:
            # ---------- 查询所有日线数据（用于聚合）----------
            q = session.query(DailyQuote).filter(DailyQuote.symbol == symbol)
            if start_date:
                q = q.filter(DailyQuote.trade_date >= start_date)
            if end_date:
                q = q.filter(DailyQuote.trade_date <= end_date)
            q = q.order_by(DailyQuote.trade_date.asc())
            daily_rows = q.all()

            if freq == "daily":
                # 日线直接转换
                items = [
                    {
                        "trade_date": r.trade_date,
                        "open": r.open,
                        "high": r.high,
                        "low": r.low,
                        "close": r.close,
                        "volume": r.volume,
                        "amount": r.amount,
                    } for r in daily_rows
                ]
            else:
                # ---------- Python 端聚合 ----------
                if not daily_rows:
                    items = []
                else:
                    # 根据 freq 计算每条记录的分组键
                    def period_key(r, freq_type):
                        d = r.trade_date
                        if freq_type == "weekly":
                            # ISO 周数，为了跨年一致，使用 (iso_year, iso_week)
                            iso = d.isocalendar()
                            return f"{iso[0]}-{iso[1]:02d}"
                        elif freq_type == "monthly":
                            return d.strftime("%Y-%m")
                        elif freq_type == "yearly":
                            return d.strftime("%Y")
                        else:
                            return d.isoformat()

                    grouped = {}
                    for r in daily_rows:
                        key = period_key(r, freq)
                        if key not in grouped:
                            grouped[key] = {
                                "first_open": r.open,
                                "last_close": r.close,
                                "high": r.high,
                                "low": r.low,
                                "volume": r.volume or 0,
                                "amount": r.amount or 0,
                                "last_date": r.trade_date,
                            }
                        else:
                            grp = grouped[key]
                            grp["last_close"] = r.close
                            grp["high"] = max(grp["high"], r.high) if r.high is not None else grp["high"]
                            grp["low"] = min(grp["low"], r.low) if r.low is not None else grp["low"]
                            grp["volume"] += r.volume or 0
                            grp["amount"] += r.amount or 0
                            grp["last_date"] = r.trade_date

                    # 转换为列表，使用 last_date 作为图表展示日期
                    items = [
                        {
                            "trade_date": val["last_date"],
                            "open": val["first_open"],
                            "high": val["high"],
                            "low": val["low"],
                            "close": val["last_close"],
                            "volume": val["volume"],
                            "amount": val["amount"],
                        }
                        for key, val in grouped.items()
                    ]
                    # 按日期排序
                    items.sort(key=lambda x: x["trade_date"])

            # ---------- 统一输出 ----------
            data = []
            for item in items:
                td = item["trade_date"]
                data.append({
                    "trade_date": td.isoformat() if isinstance(td, date) else str(td),
                    "open": float(item["open"]) if item["open"] is not None else None,
                    "high": float(item["high"]) if item["high"] is not None else None,
                    "low": float(item["low"]) if item["low"] is not None else None,
                    "close": float(item["close"]) if item["close"] is not None else None,
                    "volume": float(item["volume"]) if item["volume"] is not None else 0.0,
                    "amount": float(item["amount"]) if item["amount"] is not None else 0.0,
                })

            return {
                "symbol": symbol,
                "freq": freq,
                "start_date": min(data, key=lambda x: x["trade_date"])["trade_date"] if data else None,
                "end_date": max(data, key=lambda x: x["trade_date"])["trade_date"] if data else None,
                "count": len(data),
                "data": data,
            }
        finally:
            session.close()