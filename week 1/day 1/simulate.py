"""Simulated peer-to-peer payments platform with embedded syndicated fraud rings.

The simulator produces the SAME relational extracts a real payments platform would export. Replace the CSVs in
data/raw with real extracts that follow this schema and nothing else in the pipeline has to change.

Raw tables
    users.csv          user_id, full_name, email, phone_hash, id_doc_hash, dob, signup_date, city, kyc_level
    accounts.csv       account_id, user_id (blank = external account), bank_name, account_type, opened_date, status
    devices.csv        device_id, device_type, os, fingerprint_hash
    ip_addresses.csv   ip_id, ip_address, asn, country, is_vpn_proxy
    user_devices.csv   user_id, device_id, first_seen, last_seen, sessions
    user_ips.csv       user_id, ip_id, logins, first_login, last_login
    transactions.csv   txn_id, timestamp, from_account, to_account, amount, currency, channel, status
    _labels_users.csv / _labels_txns.csv   SIMULATION ONLY ground truth (used from Week 3 for supervised models)

Embedded fraud patterns (what the graph must later reveal):
    * rings share devices, IPs, identity documents and phone numbers (synthetic identities),
    * circular layering: money cycles A -> B -> C -> A within hours with a small haircut at each hop,
    * fan-in mule collection from victims and fan-out cash-out to external accounts,
    * deliberate legitimate look-alikes: household-shared IPs and one large office IP (false-positive traps),
    * realistic data defects: duplicates, orphan references, null/negative amounts (cleaned in Week 1 Day 2).
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from .config import CFG, Config

FIRST = ["Aarav", "Vivaan", "Aditya", "Arjun", "Sai", "Krishna", "Ishaan", "Rohan", "Karthik", "Siddharth", "Ananya",
         "Diya", "Meera", "Kavya", "Priya", "Sneha", "Lakshmi", "Divya", "Nisha", "Pooja", "Mohamed", "Aadhil", "Fatima",
         "Rahul", "Vikram", "Suresh", "Ramesh", "Anitha", "Deepa", "Gopal"]
LAST = ["Kumar", "Sharma", "Iyer", "Nair", "Reddy", "Pillai", "Das", "Singh", "Patel", "Mohan", "Raj", "Menon", "Rao",
        "Gupta", "Shah", "Khan", "Joseph", "Thomas", "Murugan", "Selvam"]
CITIES = ["Chennai", "Tiruchirappalli", "Coimbatore", "Madurai", "Bengaluru", "Hyderabad", "Mumbai", "Delhi", "Pune",
          "Kolkata", "Kochi", "Ahmedabad"]
BANKS = ["SBI", "HDFC", "ICICI", "Axis", "Canara", "IOB", "KVB", "Indian Bank"]
OS = {"mobile": ["Android 13", "Android 14", "iOS 17"], "desktop": ["Windows 11", "macOS 14", "Ubuntu 22"],
      "tablet": ["Android 13", "iPadOS 17"]}


def _h(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def simulate(cfg: Config = CFG) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(cfg.seed)
    start = pd.Timestamp(cfg.start)
    users, accounts, devices, ips, u_dev, u_ip = [], [], [], [], [], []
    lab_user = []
    ctr = {"u": 0, "a": 0, "d": 0, "i": 0}

    def nid(kind, pre, width):
        ctr[kind] += 1
        return f"{pre}{ctr[kind]:0{width}d}"

    def new_user(fraud=False, ring=None, role="legit", doc=None, phone=None, city=None):
        uid = nid("u", "U", 6)
        fn, ln = rng.choice(FIRST), rng.choice(LAST)
        domain = rng.choice(["gmail.com", "yahoo.com", "outlook.com"]) if not fraud else rng.choice(
            ["mailnesia.com", "tempmail.io", "gmail.com"])
        signup = start - pd.Timedelta(days=int(rng.integers(30, 900))) if not fraud else \
            start + pd.Timedelta(days=int(rng.integers(0, 120)))
        users.append({"user_id": uid, "full_name": f"{fn} {ln}", "email": f"{fn}.{ln}{rng.integers(1, 9999)}@{domain}".lower(),
                      "phone_hash": phone or _h(f"ph{uid}"), "id_doc_hash": doc or _h(f"id{uid}"),
                      "dob": (pd.Timestamp("1960-01-01") + pd.Timedelta(days=int(rng.integers(0, 20000)))).date(),
                      "signup_date": signup.date(), "city": city or rng.choice(CITIES),
                      "kyc_level": int(rng.choice([1, 2, 3], p=[0.2, 0.5, 0.3] if not fraud else [0.55, 0.35, 0.1]))})
        lab_user.append({"user_id": uid, "is_fraud": int(fraud), "ring_id": ring or "", "role": role})
        return uid

    def new_account(uid, opened=None, external=False):
        aid = nid("a", "A", 7)
        accounts.append({"account_id": aid, "user_id": "" if external else uid, "bank_name": rng.choice(BANKS),
                         "account_type": rng.choice(["savings", "current", "wallet"], p=[0.7, 0.1, 0.2]),
                         "opened_date": (opened or start - pd.Timedelta(days=int(rng.integers(60, 2500)))).date(),
                         "status": "active"})
        return aid

    def new_device():
        did = nid("d", "D", 6)
        dt = rng.choice(["mobile", "desktop", "tablet"], p=[0.8, 0.15, 0.05])
        devices.append({"device_id": did, "device_type": dt, "os": rng.choice(OS[dt]), "fingerprint_hash": _h(f"fp{did}")})
        return did

    def link_device(uid, did, base):
        f = base + pd.Timedelta(days=int(rng.integers(0, 60)))
        u_dev.append({"user_id": uid, "device_id": did, "first_seen": f.date(),
                      "last_seen": (f + pd.Timedelta(days=int(rng.integers(20, 300)))).date(),
                      "sessions": int(rng.integers(3, 400))})

    def new_ip(vpn=False):
        iid = nid("i", "IP", 6)
        ips.append({"ip_id": iid, "ip_address": f"{rng.integers(11, 223)}.{rng.integers(0, 255)}.{rng.integers(0, 255)}.x",
                    "asn": f"AS{rng.integers(1000, 60000)}", "country": "IN" if not vpn else rng.choice(["IN", "NL", "US", "SG"]),
                    "is_vpn_proxy": bool(vpn)})
        return iid

    def link_ip(uid, iid, base):
        f = base + pd.Timedelta(days=int(rng.integers(0, 90)))
        u_ip.append({"user_id": uid, "ip_id": iid, "logins": int(rng.integers(1, 250)), "first_login": f.date(),
                     "last_login": (f + pd.Timedelta(days=int(rng.integers(5, 250)))).date()})

    # ------------------------------------------------------------------ legitimate population
    legit = [new_user() for _ in range(cfg.n_legit_users)]
    acct_of = {}
    for uid in legit:
        acct_of[uid] = [new_account(uid) for _ in range(1 if rng.random() < 0.72 else 2)]
    # devices: ~8% share with a family member, ~5% have a second device
    for i, uid in enumerate(legit):
        did = new_device(); link_device(uid, did, start - pd.Timedelta(days=400))
        if rng.random() < 0.05:
            link_device(uid, new_device(), start - pd.Timedelta(days=200))
        if rng.random() < 0.08 and i > 0:
            link_device(uid, u_dev[int(rng.integers(0, len(u_dev)))]["device_id"], start - pd.Timedelta(days=100))
    # IPs: households of 1-4 users, plus one big office IP used by ~35 unrelated users (false-positive trap)
    i = 0
    while i < len(legit):
        k = int(rng.choice([1, 2, 3, 4], p=[0.45, 0.3, 0.15, 0.1]))
        iid = new_ip()
        for uid in legit[i:i + k]:
            link_ip(uid, iid, start - pd.Timedelta(days=300))
        i += k
    office = new_ip()
    for uid in rng.choice(legit, 35, replace=False):
        link_ip(uid, office, start - pd.Timedelta(days=150))

    ext = [new_account("", external=True) for _ in range(cfg.n_external_accounts)]

    # ------------------------------------------------------------------ fraud rings
    rings = {}
    for r in range(cfg.n_rings):
        rid = f"RING{r + 1:02d}"
        size = int(rng.integers(cfg.ring_size[0], cfg.ring_size[1] + 1))
        city = rng.choice(CITIES)
        win_start = int(rng.integers(40, 250))
        shared_docs = [_h(f"{rid}doc{k}") for k in range(max(2, size // 4))]
        shared_phone = _h(f"{rid}phone")
        members = []
        for m in range(size):
            role = "organiser" if m == 0 else ("synthetic_identity" if m % 3 == 0 else "mule")
            doc = shared_docs[m % len(shared_docs)] if role == "synthetic_identity" else None
            uid = new_user(True, rid, role, doc=doc, phone=shared_phone if m % 2 == 0 else None, city=city)
            opened = start + pd.Timedelta(days=win_start - int(rng.integers(5, 40)))
            accts = [new_account(uid, opened=opened) for _ in range(int(rng.integers(2, 4)))]
            members.append((uid, accts))
            acct_of[uid] = accts
        shared_dev = [new_device() for _ in range(int(rng.integers(2, 4)))]
        shared_ip = [new_ip(vpn=rng.random() < 0.6) for _ in range(int(rng.integers(2, 4)))]
        base = start + pd.Timedelta(days=win_start - 30)
        for uid, _ in members:
            link_device(uid, new_device(), base)
            for did in rng.choice(shared_dev, size=min(len(shared_dev), 2), replace=False):
                link_device(uid, did, base)
            for iid in rng.choice(shared_ip, size=min(len(shared_ip), 2), replace=False):
                link_ip(uid, iid, base)
        rings[rid] = {"members": members, "start": win_start, "ext": rng.choice(ext, 2, replace=False).tolist()}

    # ------------------------------------------------------------------ transactions
    txns = []
    all_legit_accts = [a for u in legit for a in acct_of[u]]
    comm = {u: int(rng.integers(0, cfg.n_communities)) for u in legit}
    by_comm = {c: [a for u in legit if comm[u] == c for a in acct_of[u]] for c in range(cfg.n_communities)}
    pop_w = rng.pareto(2.2, len(all_legit_accts)) + 1
    pop_w /= pop_w.sum()
    n_legit_tx = 55000
    src = rng.choice(all_legit_accts, n_legit_tx)
    acct_comm = {a: comm[u] for u in legit for a in acct_of[u]}
    ts = start + pd.to_timedelta(rng.uniform(0, cfg.days * 86400, n_legit_tx), unit="s")
    for k in range(n_legit_tx):
        if rng.random() < 0.82:
            pool = by_comm[acct_comm[src[k]]]
            dst = pool[int(rng.integers(0, len(pool)))]
        else:
            dst = all_legit_accts[int(rng.choice(len(all_legit_accts), p=pop_w))]
        if dst == src[k]:
            continue
        txns.append((ts[k], src[k], dst, float(np.round(rng.lognormal(7.0, 1.0), 2)), 0))

    def add(t, a, b, amt, flag=1):
        txns.append((t, a, b, float(np.round(amt, 2)), flag))

    for rid, ring in rings.items():
        mem, w0 = ring["members"], ring["start"]
        accts = [a for _, ac in mem for a in ac]
        for _ in range(int(rng.integers(25, 41))):                 # circular layering
            k = int(rng.integers(3, 6))
            cyc = list(rng.choice(accts, k, replace=False))
            t = start + pd.Timedelta(days=w0 + float(rng.uniform(0, 70)))
            amt = rng.uniform(8000, 90000)
            for h in range(k):
                add(t, cyc[h], cyc[(h + 1) % k], amt)
                amt *= rng.uniform(0.97, 0.995)
                t += pd.Timedelta(hours=float(rng.uniform(0.2, 30)))
        mule_accts = [a for _, ac in mem[1:] for a in ac]          # fan-in from victims
        for _ in range(int(rng.integers(120, 200))):
            t = start + pd.Timedelta(days=w0 + float(rng.uniform(0, 70)))
            add(t, rng.choice(all_legit_accts), rng.choice(mule_accts), rng.uniform(500, 6000))
        org = mem[0][1]                                            # fan-out cash-out
        for a in mule_accts[::2]:
            for _ in range(int(rng.integers(2, 6))):
                t = start + pd.Timedelta(days=w0 + float(rng.uniform(20, 90)))
                add(t, a, rng.choice(org), rng.uniform(15000, 60000))
        for _ in range(int(rng.integers(10, 25))):
            t = start + pd.Timedelta(days=w0 + float(rng.uniform(30, 100)))
            add(t, rng.choice(org), rng.choice(ring["ext"]), rng.uniform(40000, 150000))

    tx = pd.DataFrame(txns, columns=["timestamp", "from_account", "to_account", "amount", "is_ring_flow"])
    tx = tx.sort_values("timestamp").reset_index(drop=True)
    tx["txn_id"] = [f"T{i + 1:07d}" for i in range(len(tx))]
    tx["currency"] = "INR"
    tx["channel"] = rng.choice(["p2p_app", "bank_transfer", "card_push"], len(tx), p=[0.7, 0.2, 0.1])
    tx["status"] = rng.choice(["completed", "failed", "reversed"], len(tx), p=[0.96, 0.03, 0.01])
    labels_tx = tx[["txn_id", "is_ring_flow"]].copy()
    tx = tx[["txn_id", "timestamp", "from_account", "to_account", "amount", "currency", "channel", "status"]]
    tx["timestamp"] = tx.timestamp.dt.strftime("%Y-%m-%d %H:%M:%S")

    # ------------------------------------------------------------------ realistic defects
    dup = tx.sample(25, random_state=cfg.seed)
    orphan = tx.sample(12, random_state=cfg.seed + 1).copy()
    orphan["txn_id"] = [f"T9{i:06d}" for i in range(12)]
    orphan["to_account"] = [f"A99{i:05d}" for i in range(12)]
    tx = pd.concat([tx, dup, orphan], ignore_index=True)
    tx.loc[tx.sample(8, random_state=3).index, "amount"] = np.nan
    tx.loc[tx.sample(5, random_state=4).index, "amount"] = -tx.amount.abs()

    return {"users": pd.DataFrame(users), "accounts": pd.DataFrame(accounts), "devices": pd.DataFrame(devices),
            "ip_addresses": pd.DataFrame(ips), "user_devices": pd.DataFrame(u_dev), "user_ips": pd.DataFrame(u_ip),
            "transactions": tx, "_labels_users": pd.DataFrame(lab_user), "_labels_txns": labels_tx}


def write_raw(cfg: Config = CFG) -> dict[str, pd.DataFrame]:
    cfg.ensure()
    t = simulate(cfg)
    for name, df in t.items():
        df.to_csv(cfg.raw_dir / f"{name}.csv", index=False)
    return t
