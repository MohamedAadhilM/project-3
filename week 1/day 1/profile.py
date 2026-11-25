"""Relational data profiling and quality checks (Week 1, Day 1)."""
from __future__ import annotations

import pandas as pd

KEYS = {"users": "user_id", "accounts": "account_id", "devices": "device_id", "ip_addresses": "ip_id",
        "transactions": "txn_id"}
PUBLIC = ["users", "accounts", "devices", "ip_addresses", "user_devices", "user_ips", "transactions"]


def schema_profile(t: dict) -> pd.DataFrame:
    rows = []
    for name in PUBLIC:
        df = t[name]
        for c in df.columns:
            rows.append({"table": name, "column": c, "dtype": str(df[c].dtype), "rows": len(df),
                         "nulls": int(df[c].isna().sum() + (df[c].astype(str) == "").sum()),
                         "unique": int(df[c].nunique())})
    out = pd.DataFrame(rows)
    out["null_pct"] = (100 * out.nulls / out.rows).round(2)
    return out


def quality_checks(t: dict) -> pd.DataFrame:
    tx, ac, us = t["transactions"], t["accounts"], t["users"]
    acct_ids = set(ac.account_id)
    checks = []

    def add(check, table, n, severity, action):
        checks.append({"check": check, "table": table, "issue_rows": int(n), "severity": severity if n else "ok",
                       "planned_action": action if n else "none"})

    for name, key in KEYS.items():
        add(f"duplicate {key}", name, t[name].duplicated(key).sum(), "medium", "drop exact duplicates, keep first")
    add("duplicate (user, device) link", "user_devices", t["user_devices"].duplicated(["user_id", "device_id"]).sum(), "low", "drop")
    add("duplicate (user, ip) link", "user_ips", t["user_ips"].duplicated(["user_id", "ip_id"]).sum(), "low", "drop")
    add("missing amount", "transactions", tx.amount.isna().sum(), "high", "drop row (cannot weight an edge)")
    add("non-positive amount", "transactions", (tx.amount <= 0).sum(), "high", "drop row")
    add("from_account not in accounts", "transactions", (~tx.from_account.isin(acct_ids)).sum(), "high", "drop row (orphan edge)")
    add("to_account not in accounts", "transactions", (~tx.to_account.isin(acct_ids)).sum(), "high", "drop row (orphan edge)")
    add("self-transfer", "transactions", (tx.from_account == tx.to_account).sum(), "low", "drop row")
    add("unparseable timestamp", "transactions", pd.to_datetime(tx.timestamp, errors="coerce").isna().sum(), "high", "drop row")
    add("status not completed", "transactions", (tx.status != "completed").sum(), "info", "keep as edge property (filter later)")
    owned = ac[ac.user_id.fillna("") != ""]
    add("account.user_id not in users", "accounts", (~owned.user_id.isin(set(us.user_id))).sum(), "high", "drop account")
    add("account without owner (external)", "accounts", (ac.user_id.fillna("") == "").sum(), "info", "keep, flag is_external")
    add("user_devices.user_id not in users", "user_devices", (~t["user_devices"].user_id.isin(set(us.user_id))).sum(), "high", "drop")
    add("user_devices.device_id not in devices", "user_devices", (~t["user_devices"].device_id.isin(set(t["devices"].device_id))).sum(), "high", "drop")
    add("user_ips.ip_id not in ip_addresses", "user_ips", (~t["user_ips"].ip_id.isin(set(t["ip_addresses"].ip_id))).sum(), "high", "drop")
    return pd.DataFrame(checks)
