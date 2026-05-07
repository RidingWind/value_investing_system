"""
财务数据 ORM 模型
包含利润表、资产负债表、现金流量表、主要财务指标
"""
from datetime import datetime, UTC
from sqlalchemy import ForeignKey, Boolean, JSON, Column, Integer, String, Date, Numeric, DateTime, UniqueConstraint, \
    Index, func, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class ApiDef(Base):
    """API 定义表"""
    __tablename__ = "financial_api_def"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False, default="akshare", comment="数据源标识")
    function_name = Column(String(100), nullable=False, comment="AKShare函数名")
    chinese_name = Column(String(200), comment="中文名称")
    description = Column(Text, comment="详细说明")
    input_params = Column(JSON, default={}, comment="输入参数模板")
    output_columns = Column(JSON, default=[], comment="输出列名列表")
    date_column = Column(String(50), default="REPORT_DATE", comment="日期列名")
    filter_condition = Column(String(200), comment="可选筛选条件")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("source", "function_name", name="uq_api_def_source_func"),
    )


class IndicatorDef(Base):
    """指标定义表"""
    __tablename__ = "financial_indicator_def"

    id = Column(Integer, primary_key=True, autoincrement=True)
    standard_field = Column(String(50), unique=True, nullable=False, comment="标准字段名")
    chinese_name = Column(String(100), nullable=False, comment="中文名称")
    data_type = Column(String(20), default="float", comment="数据类型")
    unit = Column(String(20), comment="单位")
    formula = Column(Text, comment="计算公式")
    formula_version = Column(Integer, default=1, comment="公式版本号")
    report_group = Column(String(20), nullable=False, comment="报表分组标签")
    description = Column(Text, comment="说明")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), comment="更新时间", onupdate=func.now())

    __table_args__ = (
        Index("idx_indicator_report_group", "report_group"),
    )


class IndicatorApiDep(Base):
    """指标-API 依赖表（系统自动维护）"""
    __tablename__ = "financial_indicator_api_dep"

    id = Column(Integer, primary_key=True, autoincrement=True)
    indicator_id = Column(Integer, nullable=False, comment="关联 indicator_def.id")
    api_id = Column(Integer, nullable=False, comment="关联 api_def.id")
    column_name = Column(String(100), nullable=False, comment="引用的 API 输出列名")
    extracted_at = Column(DateTime, default=func.now(),comment="提取时间")

    __table_args__ = (
        UniqueConstraint("indicator_id", "api_id", "column_name", name="uq_indicator_api_dep"),
    )

# 新增 FinancialData 表，替换所有旧的分报表模型
class FinancialData(Base):
    __tablename__ = "financial_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(12), nullable=False, comment="股票代码")
    end_date = Column(Date, nullable=False, comment="报告期截止日")
    report_group = Column(String(20), nullable=False, comment="报表分组: income/balance/cashflow/indicator")
    indicator_name = Column(String(50), nullable=False, comment="指标标准字段名，如 revenue, roe")
    value = Column(String(100), comment="数值，字符串形式存入 Decimal")
    source = Column(String(20), default="dynamic_akshare", comment="数据来源")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("symbol", "end_date", "report_group", "indicator_name", name="uq_financial_data"),
        Index("idx_financial_data_symbol", "symbol"),
        Index("idx_financial_data_date", "end_date"),
        Index("idx_financial_data_report_group", "report_group"),
        Index("idx_financial_data_indicator", "indicator_name"),
    )