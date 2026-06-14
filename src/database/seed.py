import aiosqlite

from src.utils.logger import app_logger

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    phone       TEXT,
    address     TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    account_type TEXT    NOT NULL CHECK (account_type IN ('checking', 'savings', 'credit')),
    balance      REAL    NOT NULL DEFAULT 0.0,
    opened_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    from_account_id  INTEGER REFERENCES accounts(id),
    to_account_id    INTEGER REFERENCES accounts(id),
    amount           REAL    NOT NULL CHECK (amount > 0),
    transaction_type TEXT    NOT NULL CHECK (transaction_type IN ('transfer', 'deposit', 'withdrawal', 'payment')),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS loans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER NOT NULL REFERENCES customers(id),
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    loan_type     TEXT    NOT NULL CHECK (loan_type IN ('personal', 'mortgage', 'auto', 'business')),
    principal     REAL    NOT NULL CHECK (principal > 0),
    interest_rate REAL    NOT NULL CHECK (interest_rate > 0),
    status        TEXT    NOT NULL CHECK (status IN ('active', 'closed', 'defaulted')) DEFAULT 'active',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name  TEXT    NOT NULL,
    record_id   INTEGER NOT NULL,
    action      TEXT    NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by  TEXT    NOT NULL,
    changed_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

SEED_SQL = """
INSERT OR IGNORE INTO customers (id, name, email, phone, address) VALUES
  (1, 'Alice Johnson',  'alice@example.com',  '555-0101', '123 Maple St, Springfield'),
  (2, 'Bob Smith',      'bob@example.com',    '555-0102', '456 Oak Ave, Shelbyville'),
  (3, 'Carol Williams', 'carol@example.com',  '555-0103', '789 Pine Rd, Capital City'),
  (4, 'David Brown',    'david@example.com',  '555-0104', '321 Elm Blvd, Ogdenville'),
  (5, 'Eva Martinez',   'eva@example.com',    '555-0105', '654 Cedar Ln, North Haverbrook');

INSERT OR IGNORE INTO accounts (id, customer_id, account_type, balance) VALUES
  (1, 1, 'checking', 5200.00),
  (2, 1, 'savings',  12000.00),
  (3, 2, 'checking', 3400.50),
  (4, 3, 'credit',   -850.00),
  (5, 3, 'savings',  22000.00),
  (6, 4, 'checking', 1100.00),
  (7, 5, 'savings',  9500.00),
  (8, 5, 'checking', 750.00);

INSERT OR IGNORE INTO transactions (id, from_account_id, to_account_id, amount, transaction_type) VALUES
  (1, 1,    2,    500.00,  'transfer'),
  (2, 3,    1,    200.00,  'transfer'),
  (3, NULL, 1,   1000.00,  'deposit'),
  (4, 4,    NULL, 150.00,  'payment'),
  (5, 6,    7,    300.00,  'transfer'),
  (6, NULL, 8,    400.00,  'deposit'),
  (7, 2,    NULL, 250.00,  'withdrawal'),
  (8, 5,    3,    750.00,  'transfer');

INSERT OR IGNORE INTO loans (id, customer_id, account_id, loan_type, principal, interest_rate, status) VALUES
  (1, 1, 1, 'mortgage', 250000.00, 3.75, 'active'),
  (2, 2, 3, 'auto',      18000.00, 5.50, 'active'),
  (3, 3, 5, 'personal',   5000.00, 8.00, 'closed'),
  (4, 4, 6, 'business',  75000.00, 6.25, 'active'),
  (5, 5, 7, 'personal',   3000.00, 9.00, 'defaulted');

INSERT OR IGNORE INTO audit_log (id, table_name, record_id, action, changed_by) VALUES
  (1, 'customers',    1, 'INSERT', 'admin'),
  (2, 'accounts',     1, 'INSERT', 'admin'),
  (3, 'transactions', 1, 'INSERT', 'system'),
  (4, 'loans',        1, 'INSERT', 'admin'),
  (5, 'accounts',     3, 'UPDATE', 'system'),
  (6, 'loans',        3, 'UPDATE', 'admin'),
  (7, 'transactions', 8, 'INSERT', 'system'),
  (8, 'customers',    5, 'UPDATE', 'admin');
"""


async def seed_database(db_path: str = "banking.db") -> None:
    app_logger.info(f"Seeding database at {db_path}")
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.executescript(SEED_SQL)
        await db.commit()
    app_logger.info("Database seeded successfully")
