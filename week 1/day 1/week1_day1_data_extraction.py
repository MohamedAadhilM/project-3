# %% [markdown]
# # Week 1 · Day 1 — Extract Relational Transaction Data & Entity Metadata
# **Project 3 · Deep Graph Network Analytics for Syndicated Fraud Detection**
#
# **Goal:** obtain the relational datasets a fraud graph is built from — peer-to-peer transfers plus entity metadata
# (users, bank accounts, devices, IP addresses) — and profile their quality *before* modelling anything.
#
# The project plan gives no dataset, so we **simulate a payments platform with embedded fraud rings**, exported in the
# same relational shape a real platform would produce (schema documented in `src/fg/simulate.py`). To use real data,
# replace the CSVs in `data/raw/` with extracts following that schema and skip the simulation line.
#
# **Outputs:** `data/raw/*.csv`, `results/w1d1_row_counts.csv`, `results/w1d1_schema_profile.csv`,
# `results/w1d1_quality_report.csv`, `reports/figures/w1d1_overview.png`

# %%
import _bootstrap  # noqa: F401
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from fg.config import CFG
from fg.simulate import write_raw
from fg.profile import PUBLIC, schema_profile, quality_checks

CFG.ensure()
pd.options.display.float_format = "{:,.2f}".format
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": 0.25, "axes.titleweight": "bold"})

# %% [markdown]
# ## 1. Extract (simulate) the raw relational tables

# %%
tables = write_raw(CFG)                     # replace with pd.read_csv(...) calls when using real extracts
counts = pd.DataFrame({"table": PUBLIC, "rows": [len(tables[n]) for n in PUBLIC],
                       "columns": [tables[n].shape[1] for n in PUBLIC]})
counts.to_csv(CFG.results_dir / "w1d1_row_counts.csv", index=False)
print(counts.to_string(index=False))
print("\nGround-truth label files (simulation only, used from Week 3): _labels_users.csv, _labels_txns.csv")

# %% [markdown]
# ## 2. Understand the schema
# Entities and how they relate: a **user** owns **accounts**; money moves **account → account**; a user also appears on
# **devices** and **IP addresses**. Those last two links are where fraud rings leave footprints.

# %%
prof = schema_profile(tables)
prof.to_csv(CFG.results_dir / "w1d1_schema_profile.csv", index=False)
print(prof[prof.table == "transactions"].to_string(index=False))

# %% [markdown]
# ## 3. Initial data-quality checks
# Real extracts always have defects. Each check below is a rule the Day 2 cleaning step will act on.

# %%
qc = quality_checks(tables)
qc.to_csv(CFG.results_dir / "w1d1_quality_report.csv", index=False)
print(qc[qc.issue_rows > 0].to_string(index=False))
print(f"\n{(qc.issue_rows > 0).sum()} of {len(qc)} checks found issues; total flagged rows: {qc.issue_rows.sum()}")

# %% [markdown]
# ## 4. First look at the data

# %%
tx = tables["transactions"].copy()
tx["timestamp"] = pd.to_datetime(tx.timestamp)
tx = tx[(tx.amount > 0)]
fig, ax = plt.subplots(1, 3, figsize=(15, 3.8))
tx.set_index("timestamp").resample("W").size().plot(ax=ax[0], color="#1f77b4")
ax[0].set_title("Transactions per week"); ax[0].set_xlabel("")
ax[1].hist(np.log10(tx.amount), bins=60, color="#1f77b4")
ax[1].set_title("Transaction amount (log10 INR)"); ax[1].set_xlabel("log10(amount)")
ud = tables["user_devices"].groupby("device_id").user_id.nunique().value_counts().sort_index()
ax[2].bar(ud.index.astype(str), ud.values, color="#d62728"); ax[2].set_yscale("log")
ax[2].set_title("Users per device (log scale)\nshared devices are a ring footprint"); ax[2].set_xlabel("users sharing a device")
plt.tight_layout(); plt.savefig(CFG.fig_dir / "w1d1_overview.png", bbox_inches="tight"); plt.show()

shared = int((tables["user_devices"].groupby("device_id").user_id.nunique() >= 3).sum())
print(f"Devices used by 3+ users: {shared} | median transaction: {tx.amount.median():,.0f} INR | "
      f"largest: {tx.amount.max():,.0f} INR")
