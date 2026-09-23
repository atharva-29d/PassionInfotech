"""
verify_load.py — quick sanity checks after running load_nsl_kdd.py

Usage:
    python verify_load.py
"""

try:
    from Atharva.backend.ingestion.load_nsl_kdd import get_engine
except ModuleNotFoundError:
    from load_nsl_kdd import get_engine
from sqlalchemy import text

engine = get_engine()

with engine.connect() as conn:
    total = conn.execute(text("SELECT COUNT(*) FROM network_event")).scalar()
    attacks = conn.execute(text("SELECT COUNT(*) FROM network_event WHERE is_attack = TRUE")).scalar()
    protocols = conn.execute(text(
        "SELECT protocol_type, COUNT(*) FROM network_event GROUP BY protocol_type"
    )).fetchall()

    splits = conn.execute(text(
        "SELECT split, COUNT(*) FROM network_event GROUP BY split"
    )).fetchall()

    print(f"Total events: {total}")
    print(f"Attack events: {attacks} ({attacks / total:.1%})")
    print("By split:")
    for row in splits:
        print(f"  {row[0]}: {row[1]}")
    print("By protocol:")
    for row in protocols:
        print(f"  {row[0]}: {row[1]}")

    sample = conn.execute(text("SELECT * FROM network_event LIMIT 3")).fetchall()
    print("\nSample rows:")
    for row in sample:
        print(row)
