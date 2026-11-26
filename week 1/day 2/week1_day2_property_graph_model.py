# %% [markdown]
# # Week 1 · Day 2 — Property-Graph Data Model
# **Project 3 · Deep Graph Network Analytics for Syndicated Fraud Detection**
#
# **Goal:** design the property graph (nodes, edges, properties) and transform the cleaned relational tables into it.
#
# **Design choices that matter for fraud detection**
# * **Accounts are the money nodes**; a transfer is an *edge* `Account -[TRANSFERRED_TO]-> Account`, so cycles and flows are
#   native graph structures.
# * **Devices, IPs, phones and identity documents are nodes, not columns.** Two fraudsters who share a device or an ID document
#   then sit two hops apart — exactly what community detection will exploit in Week 2.
#
# **Inputs:** `data/raw/*.csv` (Day 1) · **Outputs:** `data/graph/*.csv`, `results/w1d2_cleaning_log.csv`,
# `results/w1d2_graph_schema.json`, `results/w1d2_relational_to_graph_mapping.csv`, `results/w1d2_graph_counts.csv`,
# `reports/figures/w1d2_graph_schema.png`

# %%
import _bootstrap  # noqa: F401
import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

from fg.config import CFG
from fg.transform import SCHEMA, clean, build_graph, write_graph_csv, referential_check

CFG.ensure()
tables = {n: pd.read_csv(CFG.raw_dir / f"{n}.csv") for n in
          ["users", "accounts", "devices", "ip_addresses", "user_devices", "user_ips", "transactions"]}
print({k: len(v) for k, v in tables.items()})

# %% [markdown]
# ## 1. Clean the data (rules planned on Day 1)

# %%
cleaned, log = clean(tables)
log.to_csv(CFG.results_dir / "w1d2_cleaning_log.csv", index=False)
print(log.to_string(index=False))
print(f"\nTransactions: {len(tables['transactions'])} -> {len(cleaned['transactions'])} "
      f"({len(tables['transactions']) - len(cleaned['transactions'])} removed)")

# %% [markdown]
# ## 2. Build node and edge tables

# %%
g = build_graph(cleaned)
write_graph_csv(g, CFG.graph_dir)
counts = pd.DataFrame(
    [("node", k, spec["file"], len(g[spec["file"][:-4]])) for k, spec in SCHEMA["nodes"].items()] +
    [("edge", k, spec["file"], len(g[spec["file"][:-4]])) for k, spec in SCHEMA["edges"].items()],
    columns=["kind", "label", "file", "count"])
counts.to_csv(CFG.results_dir / "w1d2_graph_counts.csv", index=False)
print(counts.to_string(index=False))
print(f"\nTotal nodes: {counts[counts.kind == 'node']['count'].sum():,} | total edges: {counts[counts.kind == 'edge']['count'].sum():,}")

# %% [markdown]
# ## 3. Referential integrity: every edge endpoint must exist as a node

# %%
ref = referential_check(g)
print(ref.to_string(index=False))
assert (ref.missing_src.sum() + ref.missing_dst.sum()) == 0, "dangling edges found"
print("\nNo dangling edges.")

# %% [markdown]
# ## 4. Document the model: schema file, mapping table and diagram

# %%
(CFG.results_dir / "w1d2_graph_schema.json").write_text(json.dumps(SCHEMA, indent=2))
mapping = pd.DataFrame([
    ("users", "User node", "user_id, full_name, email, dob, signup_date, city, kyc_level"),
    ("users.phone_hash", "Phone node + (User)-[HAS_PHONE]->(Phone)", "phone_hash (shared phones link users)"),
    ("users.id_doc_hash", "IdentityDoc node + (User)-[HAS_ID_DOC]->(IdentityDoc)", "id_doc_hash (shared documents = synthetic identities)"),
    ("accounts", "Account node (+ is_external flag)", "account_id, bank_name, account_type, opened_date, status, is_external"),
    ("accounts.user_id", "(User)-[OWNS]->(Account)", "none"),
    ("devices", "Device node", "device_id, device_type, os, fingerprint_hash"),
    ("user_devices", "(User)-[USES_DEVICE]->(Device)", "first_seen, last_seen, sessions"),
    ("ip_addresses", "IPAddress node", "ip_id, ip_address, asn, country, is_vpn_proxy"),
    ("user_ips", "(User)-[LOGGED_IN_FROM]->(IPAddress)", "logins, first_login, last_login"),
    ("transactions", "(Account)-[TRANSFERRED_TO]->(Account)", "txn_id, ts, amount, currency, channel, status")],
    columns=["relational_source", "graph_element", "properties"])
mapping.to_csv(CFG.results_dir / "w1d2_relational_to_graph_mapping.csv", index=False)

pos = {"User": (0.5, 0.5), "Account": (0.18, 0.12), "Device": (0.82, 0.12), "IPAddress": (0.9, 0.62),
       "Phone": (0.5, 0.95), "IdentityDoc": (0.1, 0.62)}
col = {"User": "#1f77b4", "Account": "#2ca02c", "Device": "#d62728", "IPAddress": "#f2a900", "Phone": "#9467bd", "IdentityDoc": "#8c564b"}
fig, ax = plt.subplots(figsize=(10, 6.2)); ax.set_xlim(-0.05, 1.05); ax.set_ylim(-0.05, 1.08); ax.axis("off")
for e, s in SCHEMA["edges"].items():
    a, b = pos[s["src"]], pos[s["dst"]]
    if s["src"] == s["dst"]:
        ax.annotate("", xy=(a[0] + 0.045, a[1] - 0.075), xytext=(a[0] - 0.045, a[1] - 0.075),
                    arrowprops=dict(arrowstyle="-|>", connectionstyle="arc3,rad=1.5", color="#d62728", lw=2.4, mutation_scale=18))
        ax.text(a[0], a[1] - 0.27, e + "\n(txn_id, ts, amount, channel, status)", ha="center", fontsize=8.5, color="#d62728")
    else:
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=16, shrinkA=30, shrinkB=30, color="#555", lw=1.5))
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.03, e, ha="center", fontsize=8.5, color="#333",
                bbox=dict(fc="white", ec="none", pad=1))
for n, (x, y) in pos.items():
    ax.scatter([x], [y], s=4200, color=col[n], edgecolor="k", zorder=3)
    ax.text(x, y, n, ha="center", va="center", fontsize=9, color="white", fontweight="bold", zorder=4)
ax.set_title("Property-graph schema: 6 node labels, 6 relationship types", fontweight="bold")
plt.tight_layout(); plt.savefig(CFG.fig_dir / "w1d2_graph_schema.png", dpi=160, bbox_inches="tight"); plt.show()
