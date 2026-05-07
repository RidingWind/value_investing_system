CREATE TABLE IF NOT EXISTS daily_quotes (
    id SERIAL PRIMARY KEY,                     -- PostgreSQL 自增主键（SQLite 用 INTEGER PRIMARY KEY AUTOINCREMENT）
    symbol VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(15, 4),
    high DECIMAL(15, 4),
    low DECIMAL(15, 4),
    close DECIMAL(15, 4),
    volume DECIMAL(20, 2),
    amount DECIMAL(20, 2),
    adj_factor DECIMAL(15, 6) DEFAULT 1.0,
    source VARCHAR(20) DEFAULT 'akshare',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_quotes_symbol ON daily_quotes(symbol);
CREATE INDEX IF NOT EXISTS idx_daily_quotes_date ON daily_quotes(trade_date);