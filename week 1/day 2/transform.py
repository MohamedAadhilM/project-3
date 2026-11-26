"""Relational -> property-graph transformation (Week 1, Day 2).

SCHEMA is the single source of truth: Day 3 generates Neo4j scripts from it and Day 4 generates the Kuzu DDL from it.
Types: STRING, INT64, DOUBLE, DATE, TIMESTAMP, BOOLEAN.
"""
from __future__ import annotations

import pandas as pd

SCHEMA = {
    "nodes": {
        "User": {"key": "user_id", "file": "nodes_user.csv",
                 "props": {"user_id": "STRING", "full_name": "STRING", "email": "STRING", "dob": "DATE",
                           "signup_date": "DATE", "city": "STRING", "kyc_level": "INT64"}},
        "Account": {"key": "account_id", "file": "nodes_account.csv",
                    "props": {"account_id": "STRING", "bank_name": "STRING", "account_type": "STRING",
                              "opened_date": "DATE", "status": "STRING", "is_external": "BOOLEAN"}},
        "Device": {"key": "device_id", "file": "nodes_device.csv",
                   "props": {"device_id": "STRING", "device_type": "STRING", "os": "STRING", "fingerprint_hash": "STRING"}},
        "IPAddress": {"key": "ip_id", "file": "nodes_ip.csv",
                      "props": {"ip_id": "STRING", "ip_address": "STRING", "asn": "STRING", "country": "STRING",
                                "is_vpn_proxy": "BOOLEAN"}},
        "Phone": {"key": "phone_hash", "file": "nodes_phone.csv", "props": {"phone_hash": "STRING"}},
        "IdentityDoc": {"key": "id_doc_hash", "file": "nodes_iddoc.csv", "props": {"id_doc_hash": "STRING"}},
    },
    "edges": {
        "OWNS": {"src": "User", "dst": "Account", "file": "edges_owns.csv", "props": {}},
        "USES_DEVICE": {"src": "User", "dst": "Device", "file": "edges_uses_device.csv",
                        "props": {"first_seen": "DATE", "last_seen": "DATE", "sessions": "INT64"}},
        "LOGGED_IN_FROM": {"src": "User", "dst": "IPAddress", "file": "edges_logged_in_from.csv",
                           "props": {"logins": "INT64", "first_login": "DATE", "last_login": "DATE"}},
        "HAS_PHONE": {"src": "User", "dst": "Phone", "file": "edges_has_phone.csv", "props": {}},
        "HAS_ID_DOC": {"src": "User", "dst": "IdentityDoc", "file": "edges_has_id_doc.csv", "props": {}},
        "TRANSFERRED_TO": {"src": "Account", "dst": "Account", "file": "edges_transferred_to.csv",
                           "props": {"txn_id": "STRING", "ts": "TIMESTAMP", "amount": "DOUBLE", "currency": "STRING",
                                     "channel": "STRING", "status": "STRING"}},
    },
}


def clean(t: dict) -> tuple[dict, pd.DataFrame]:
    """Apply the Day 1 quality rules. Returns cleaned tables and a log of every removal."""
    log = []

    def step(name, df, mask_drop):
        log.append({"rule": name, "rows_removed": int(mask_drop.sum())})
        return df[~mask_drop]

    c = {k: v.copy() for k, v in t.items() if not k.startswith("_")}
    tx = c["transactions"]
    tx = step("duplicate txn_id", tx, tx.duplicated("txn_id"))
    tx = step("missing amount", tx, tx.amount.isna())
    tx = step("non-positive amount", tx, tx.amount <= 0)
    acct = set(c["accounts"].account_id)
    tx = step("orphan from_account", tx, ~tx.from_account.isin(acct))
    tx = step("orphan to_account", tx, ~tx.to_account.isin(acct))
    tx = step("self-transfer", tx, tx.from_account == tx.to_account)
    tx = tx.assign(timestamp=pd.to_datetime(tx.timestamp, errors="coerce"))
    tx = step("unparseable timestamp", tx, tx.timestamp.isna())
    c["transactions"] = tx
    for name, keys in (("user_devices", ["user_id", "device_id"]), ("user_ips", ["user_id", "ip_id"])):
        c[name] = step(f"duplicate {name} link", c[name], c[name].duplicated(keys))
    return c, pd.DataFrame(log)


def build_graph(c: dict) -> dict[str, pd.DataFrame]:
    """Turn cleaned relational tables into node and edge frames (first two edge columns = source, destination)."""
    us, ac = c["users"], c["accounts"]
    g = {}
    g["nodes_user"] = us[["user_id", "full_name", "email", "dob", "signup_date", "city", "kyc_level"]]
    acc = ac.copy()
    acc["is_external"] = acc.user_id.fillna("") == ""
    g["nodes_account"] = acc[["account_id", "bank_name", "account_type", "opened_date", "status", "is_external"]]
    g["nodes_device"] = c["devices"][["device_id", "device_type", "os", "fingerprint_hash"]]
    g["nodes_ip"] = c["ip_addresses"][["ip_id", "ip_address", "asn", "country", "is_vpn_proxy"]]
    g["nodes_phone"] = pd.DataFrame({"phone_hash": us.phone_hash.unique()})
    g["nodes_iddoc"] = pd.DataFrame({"id_doc_hash": us.id_doc_hash.unique()})
    own = acc[~acc.is_external]
    g["edges_owns"] = own[["user_id", "account_id"]].rename(columns={"user_id": "src_id", "account_id": "dst_id"})
    ud = c["user_devices"]
    g["edges_uses_device"] = ud[["user_id", "device_id", "first_seen", "last_seen", "sessions"]].rename(
        columns={"user_id": "src_id", "device_id": "dst_id"})
    ui = c["user_ips"]
    g["edges_logged_in_from"] = ui[["user_id", "ip_id", "logins", "first_login", "last_login"]].rename(
        columns={"user_id": "src_id", "ip_id": "dst_id"})
    g["edges_has_phone"] = us[["user_id", "phone_hash"]].rename(columns={"user_id": "src_id", "phone_hash": "dst_id"})
    g["edges_has_id_doc"] = us[["user_id", "id_doc_hash"]].rename(columns={"user_id": "src_id", "id_doc_hash": "dst_id"})
    tx = c["transactions"]
    e = tx[["from_account", "to_account", "txn_id", "timestamp", "amount", "currency", "channel", "status"]].rename(
        columns={"from_account": "src_id", "to_account": "dst_id", "timestamp": "ts"})
    e["ts"] = e.ts.dt.strftime("%Y-%m-%d %H:%M:%S")
    g["edges_transferred_to"] = e
    return g


def write_graph_csv(g: dict, directory) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, df in g.items():
        df.to_csv(directory / f"{name}.csv", index=False)


def referential_check(g: dict) -> pd.DataFrame:
    """Every edge endpoint must exist as a node. Returns one row per edge type."""
    rows = []
    for etype, spec in SCHEMA["edges"].items():
        e = g[spec["file"].replace(".csv", "")]
        sn, dn = SCHEMA["nodes"][spec["src"]], SCHEMA["nodes"][spec["dst"]]
        src_keys = set(g[sn["file"].replace(".csv", "")][sn["key"]])
        dst_keys = set(g[dn["file"].replace(".csv", "")][dn["key"]])
        rows.append({"edge": etype, "edges": len(e), "missing_src": int((~e.src_id.isin(src_keys)).sum()),
                     "missing_dst": int((~e.dst_id.isin(dst_keys)).sum())})
    return pd.DataFrame(rows)
