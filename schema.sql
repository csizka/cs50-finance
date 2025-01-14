CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, username TEXT NOT NULL, hash TEXT NOT NULL, cash NUMERIC NOT NULL DEFAULT 10000.00);
CREATE UNIQUE INDEX username ON users (username);
CREATE TABLE symbols (
id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
symbol VARCHAR(5) NOT NULL
);
CREATE TABLE purchases
  (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  user_id INTEGER NOT NULL,
  symbol_id INTEGER NOT NULL,
  amount INTEGER NOT NULL,
  price NUMERIC NOT NULL,
  time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON UPDATE CASCADE
  );
CREATE TABLE stock_balance
(user_id INTEGER NOT NULL,
symbol_id INTEGER NOT NULL,
amount NUMERIC NOT NULL,
FOREIGN KEY (user_id) REFERENCES users(id),
FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON UPDATE CASCADE
);
CREATE UNIQUE INDEX symbol ON symbols (symbol);
CREATE INDEX balance_user_id ON stock_balance (user_id);
CREATE INDEX balance_symbol_id ON stock_balance (symbol_id);
CREATE INDEX purchase_user_id ON purchases (user_id);
CREATE TABLE cash_transactions (
id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  user_id INTEGER NOT NULL,
  amount INTEGER NOT NULL,
  time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX cash_user_id ON cash_transactions (user_id);
