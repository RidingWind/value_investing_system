import decimal
from sqlalchemy.types import TypeDecorator, String, Numeric

class SqliteNumeric(TypeDecorator):
    impl = Numeric  # 存储为字符串，精确无损失

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return decimal.Decimal(value)
        return value