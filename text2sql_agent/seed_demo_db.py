"""
seed_demo_db.py — creates a small SQLite database with sample data
so you can run the agent end-to-end without any cloud setup.

Run once:  python seed_demo_db.py
"""
import os
import sqlite3

DB_PATH = "demo.db"

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# --- Schema ---
cur.executescript("""
CREATE TABLE supplychain (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    region       TEXT NOT NULL,
    stock        INTEGER NOT NULL
);

CREATE TABLE sales (
    sale_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    region        TEXT NOT NULL,
    sale_date     DATE NOT NULL,
    FOREIGN KEY (product_id) REFERENCES supplychain(product_id)
);
""")

# --- Sample products ---
products = [
    (1, "hairfall shampoo", "Germany", 1500),
    (2, "hairfall shampoo", "France",  1200),
    (3, "hairfall shampoo", "India",   2000),
    (4, "face wash",        "Germany", 800),
    (5, "conditioner",      "Germany", 600),
]
cur.executemany(
    "INSERT INTO supplychain VALUES (?, ?, ?, ?)", products
)

# --- Sample sales (intentionally biased toward Germany / hairfall shampoo) ---
sales = [
    # Germany — hairfall shampoo (product_id=1)
    ("Hans Müller",     1, 142, "Germany", "2024-03-12"),
    ("Anna Schmidt",    1,  87, "Germany", "2024-03-15"),
    ("Lukas Weber",     1,  64, "Germany", "2024-03-20"),
    ("Hans Müller",     1,  35, "Germany", "2024-04-02"),  # Hans buys again
    ("Sophie Becker",   1,  21, "Germany", "2024-04-10"),
    ("Anna Schmidt",    1,  18, "Germany", "2024-04-15"),  # Anna buys again
    ("Felix Hoffmann",  1,   9, "Germany", "2024-04-22"),

    # France — hairfall shampoo (product_id=2) — should be excluded
    ("Marie Dupont",    2,  55, "France",  "2024-03-18"),
    ("Pierre Martin",   2,  41, "France",  "2024-03-25"),

    # Germany — face wash (product_id=4) — different product, same region
    ("Hans Müller",     4,  10, "Germany", "2024-03-30"),
    ("Lena Fischer",    4,  25, "Germany", "2024-04-05"),

    # India — hairfall shampoo (product_id=3) — different region
    ("Rahul Sharma",    3, 200, "India",   "2024-03-10"),
    ("Priya Singh",     3, 150, "India",   "2024-03-14"),
]
cur.executemany(
    "INSERT INTO sales (customer_name, product_id, quantity, region, sale_date) "
    "VALUES (?, ?, ?, ?, ?)",
    sales
)

conn.commit()
conn.close()

print(f"Seeded {DB_PATH} with {len(products)} products and {len(sales)} sales rows.")
print("Now run:  python main.py")
