from datetime import datetime, UTC
import logging
from decimal import Decimal, InvalidOperation

import pandas as pd
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import Pool
from typing import Optional
from .models import Base, ApiDef, IndicatorApiDep, IndicatorDef, FinancialData
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class FinancialStorage:
    def __init__(self, database_url: str):
        is_sqlite = database_url.startswith("sqlite")
        if is_sqlite:
            self.engine = create_engine(
                database_url,
                echo=False,
                connect_args={"check_same_thread": False},
            )
            @event.listens_for(self.engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, _connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.close()
        else:
            self.engine = create_engine(
                database_url,
                connect_args={"connect_timeout": 30},
                echo=False,
                pool_size=20,
                max_overflow=10,
            )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    @contextmanager
    def _session(self):
        session = self.Session()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ---------- API 定义管理 ----------
    def get_all_api_defs(self):
        with self._session() as session:
            return session.query(ApiDef).all()

    def get_api_def(self, api_id: int):
        with self._session() as session:
            return session.query(ApiDef).filter_by(id=api_id).first()

    def save_api_def(self, data: dict) -> int:
        with self._session() as session:
            if 'id' in data:
                obj = session.query(ApiDef).filter_by(id=data['id']).first()
                if obj is None:
                    raise ValueError(f"ApiDef id={data['id']} 不存在")
                for k, v in data.items():
                    setattr(obj, k, v)
                session.commit()
                return obj.id
            # 先按唯一键查找是否已存在；存在则返回现有 id
            existing = (
                session.query(ApiDef)
                .filter_by(source=data.get('source'), function_name=data.get('function_name'))
                .first()
            )
            if existing is not None:
                for k, v in data.items():
                    setattr(existing, k, v)
                session.commit()
                return existing.id
            obj = ApiDef(**data)
            session.add(obj)
            session.commit()
            return obj.id

    def delete_api_def(self, api_id: int):
        with self._session() as session:
            session.query(ApiDef).filter_by(id=api_id).delete()
            session.query(IndicatorApiDep).filter_by(api_id=api_id).delete()
            session.commit()

    # ---------- 指标定义管理 ----------
    def get_all_indicators(self, report_group: str = None):
        with self._session() as session:
            q = session.query(IndicatorDef)
            if report_group:
                q = q.filter_by(report_group=report_group)
            return q.order_by(IndicatorDef.standard_field).all()

    def get_indicator(self, indicator_id: int):
        with self._session() as session:
            return session.query(IndicatorDef).filter_by(id=indicator_id).first()

    # def save_indicator(self, data: dict) -> int:
    #     with self._session() as session:
    #         if 'id' in data:
    #             obj = session.query(IndicatorDef).filter_by(id=data['id']).first()
    #             if obj is None:
    #                 raise ValueError(f"IndicatorDef id={data['id']} 不存在")
    #             for k, v in data.items():
    #                 setattr(obj, k, v)
    #         else:
    #             obj = IndicatorDef(**data)
    #             session.add(obj)
    #         session.flush()  # 获取 id
    #         indicator_id = obj.id
    #         # 自动解析依赖
    #         self._update_indicator_deps(indicator_id, data.get('formula', ''))
    #         session.commit()
    #         return indicator_id

    def delete_indicator(self, indicator_id: int):
        with self._session() as session:
            session.query(IndicatorDef).filter_by(id=indicator_id).delete()
            session.query(IndicatorApiDep).filter_by(indicator_id=indicator_id).delete()
            session.commit()

    # ---------- 依赖管理 ----------
    # def _update_indicator_deps(self, indicator_id: int, formula: str):
    #     from app.core.data.financial.dependency_parser import FormulaDependencyParser
    #     with self._session() as session:
    #         session.query(IndicatorApiDep).filter_by(indicator_id=indicator_id).delete()
    #         deps = FormulaDependencyParser.parse(formula)
    #         for dep in deps:
    #             api_def = session.query(ApiDef).filter_by(function_name=dep['function_name']).first()
    #             if api_def:
    #                 dep_record = IndicatorApiDep(
    #                     indicator_id=indicator_id,
    #                     api_id=api_def.id,
    #                     column_name=dep['column_name']
    #                 )
    #                 session.add(dep_record)
    #             else:
    #                 logging.warning(f"公式中引用了未注册的API: {dep['function_name']}")
    #         session.commit()

    def save_indicator(self, data: dict, deps: list = None) -> int:
        """保存指标定义。deps 为 [{"api_id":1, "column_name":"col"}, ...] 直接更新依赖；
        若未提供 deps，则根据 formula 自动解析依赖。所有操作均在同一会话中完成。
        """
        with self._session() as session:
            if 'id' in data:
                obj = session.query(IndicatorDef).filter_by(id=data['id']).first()
                if obj is None:
                    raise ValueError(f"IndicatorDef id={data['id']} 不存在")
                for k, v in data.items():
                    setattr(obj, k, v)
            else:
                # standard_field 有唯一约束，若已存在则更新而非插入
                existing = session.query(IndicatorDef).filter_by(standard_field=data.get('standard_field')).first()
                if existing is not None:
                    for k, v in data.items():
                        setattr(existing, k, v)
                    obj = existing
                else:
                    obj = IndicatorDef(**data)
                    session.add(obj)
            session.flush()  # 获取 obj.id
            indicator_id = obj.id

            # ---------- 统一处理依赖 ----------
            session.query(IndicatorApiDep).filter_by(indicator_id=indicator_id).delete()

            if deps is not None:
                for dep in deps:
                    api_id = dep.get('api_id')
                    column_name = dep.get('column_name')
                    if api_id and column_name:
                        api = session.query(ApiDef).filter_by(id=api_id).first()
                        if api:
                            session.add(IndicatorApiDep(
                                indicator_id=indicator_id,
                                api_id=api_id,
                                column_name=column_name
                            ))
            else:
                formula = data.get('formula', '')
                if formula:
                    from app.core.data.financial.dependency_parser import FormulaDependencyParser
                    parsed_deps = FormulaDependencyParser.parse(formula)
                    for dep in parsed_deps:
                        api = session.query(ApiDef).filter_by(function_name=dep['function_name']).first()
                        if api:
                            session.add(IndicatorApiDep(
                                indicator_id=indicator_id,
                                api_id=api.id,
                                column_name=dep['column_name']
                            ))
                        else:
                            logging.warning(f"公式引用了未注册的API: {dep['function_name']}")
            session.commit()
            return indicator_id

    def get_indicator_deps(self, indicator_id: int):
        session = self.Session()
        try:
            deps = session.query(IndicatorApiDep).filter_by(indicator_id=indicator_id).all()
            result = []
            for d in deps:
                api = session.query(ApiDef).filter_by(id=d.api_id).first()
                result.append({
                    'function_name': api.function_name if api else '未知',
                    'column_name': d.column_name,
                    'api_id': d.api_id
                })
            return result
        finally:
            session.close()

    def get_affected_indicators(self, api_id: int):
        """查询某个 API 被哪些指标依赖"""
        session = self.Session()
        try:
            deps = session.query(IndicatorApiDep).filter_by(api_id=api_id).all()
            result = []
            for d in deps:
                ind = session.query(IndicatorDef).filter_by(id=d.indicator_id).first()
                if ind:
                    result.append({
                        'indicator_id': ind.id,
                        'standard_field': ind.standard_field,
                        'chinese_name': ind.chinese_name,
                        'column_name': d.column_name
                    })
            return result
        finally:
            session.close()

    def has_api_defs(self):
        session = self.Session()
        try:
            return session.query(ApiDef).count() > 0
        finally:
            session.close()

    @staticmethod
    def to_decimal_or_none(val):
        if val is None or val == '':
            return None
        try:
            return Decimal(str(val))
        except (InvalidOperation, ValueError, TypeError):
            return None

    def save_indicator_data(self, df: pd.DataFrame) -> int:
        """存储窄表指标数据，df 必须包含列: symbol, end_date, report_group, indicator_name, value, source"""
        if df.empty:
            return 0
        session = self.Session()
        try:
            count = 0
            for _, row in df.iterrows():
                symbol = row['symbol']
                end_date = row['end_date']
                report_group = row.get('report_group', 'indicator')
                indicator_name = row['indicator_name']
                source = row.get('source', 'dynamic_akshare')
                raw_value = row['value']

                dec_val = self.to_decimal_or_none(raw_value)
                if dec_val is None:
                    continue
                val_str = str(dec_val)

                existing = session.query(FinancialData).filter_by(
                    symbol=symbol,
                    end_date=end_date,
                    report_group=report_group,
                    indicator_name=indicator_name
                ).first()
                if existing:
                    existing.value = val_str
                    existing.source = source
                    existing.created_at = datetime.now(UTC)
                else:
                    rec = FinancialData(
                        symbol=symbol,
                        end_date=end_date,
                        report_group=report_group,
                        indicator_name=indicator_name,
                        value=val_str,
                        source=source
                    )
                    session.add(rec)
                count += 1
            session.commit()
            logger.info(f"成功存储 {count} 条指标数据（窄表）")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"指标数据存储失败: {e}")
            raise
        finally:
            session.close()

    def get_summary(self) -> dict:
        session = self.Session()
        try:
            from sqlalchemy import func
            rows = session.query(
                FinancialData.report_group, func.count(FinancialData.id)
            ).group_by(FinancialData.report_group).all()
            summary = {group: cnt for group, cnt in rows}
            return {
                "income_records": summary.get("income", 0),
                "balance_records": summary.get("balance", 0),
                "cashflow_records": summary.get("cashflow", 0),
                "indicator_records": summary.get("indicator", 0),
            }
        finally:
            session.close()

    def get_symbol_range(self, symbol: str) -> Optional[dict]:
        session = self.Session()
        try:
            from sqlalchemy import func
            result = session.query(
                func.min(FinancialData.end_date),
                func.max(FinancialData.end_date),
                func.count(FinancialData.id)
            ).filter(FinancialData.symbol == symbol).first()
            if not result or result[2] == 0:
                return None
            return {
                "symbol": symbol,
                "start_date": str(result[0]),
                "end_date": str(result[1]),
                "record_count": result[2]
            }
        finally:
            session.close()
    #
    # def update_indicator_deps(self, indicator_id: int, deps: list):
    #     """前端传递的依赖列表: [{"api_id": 1, "column_name": "OPERATE_INCOME"}, ...]"""
    #     session = self.Session()
    #     try:
    #         # 清除旧依赖
    #         session.query(IndicatorApiDep).filter_by(indicator_id=indicator_id).delete()
    #         for dep in deps:
    #             api_id = dep['api_id']
    #             column_name = dep['column_name']
    #             # 验证 api_id 是否存在
    #             api = session.query(ApiDef).filter_by(id=api_id).first()
    #             if not api:
    #                 logger.warning(f"无效的 api_id: {api_id}，跳过")
    #                 continue
    #             rec = IndicatorApiDep(
    #                 indicator_id=indicator_id,
    #                 api_id=api_id,
    #                 column_name=column_name
    #             )
    #             session.add(rec)
    #         session.commit()
    #     except Exception as e:
    #         session.rollback()
    #         logger.error(f"更新指标依赖失败: {e}")
    #         raise
    #     finally:
    #         session.close()