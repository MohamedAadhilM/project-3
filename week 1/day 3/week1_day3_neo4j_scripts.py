# %% [markdown]
# # Week 1 · Day 3 — Neo4j Scripts, Constraints & Bulk-Import Files
# **Project 3 · Deep Graph Network Analytics for Syndicated Fraud Detection**
#
# **Goal:** prepare everything needed to load the property graph into **Neo4j** (the engine named in the project plan):
# uniqueness constraints, indexes, an online `LOAD CSV` script, header-annotated files for the fast offline
# `neo4j-admin import`, a Docker Compose file (with the APOC and Graph Data Science plugins Week 2 needs), and validation queries.
#
# All scripts are **generated from the one schema definition** (`fg.transform.SCHEMA`), so the model, the Neo4j scripts and the
# Day 4 loader cannot drift apart.
#
# > Honest note: these scripts are generated and cross-checked by code here, but a Neo4j server could not be started in the
# > build environment (no Docker). Day 4 therefore *runs* the identical load logic on an embedded graph database (Kuzu).
# > Run `docker compose up -d` on your machine to execute the Neo4j path.
#
# **Inputs:** `data/graph/*.csv` (Day 2) · **Outputs:** `neo4j/*.cypher`, `docker-compose.yml`, `data/neo4j_import/*`,
# `results/w1d3_artifact_manifest.csv`, `results/w1d3_expected_counts.csv`, `results/w1d3_consistency_checks.csv`

# %%
import _bootstrap  # noqa: F401
import pandas as pd

from fg.config import CFG, ROOT
from fg.transform import SCHEMA
from fg import neo4j_gen

CFG.ensure()

# %% [markdown]
# ## 1. Generate the scripts

# %%
manifest = neo4j_gen.write_all(CFG.graph_dir, CFG.neo4j_dir, ROOT)
art = pd.DataFrame([
    ("neo4j/constraints.cypher", "Uniqueness constraints for every node key"),
    ("neo4j/indexes.cypher", "Secondary indexes (city, VPN flag, transfer time and amount)"),
    ("neo4j/load_csv.cypher", "Online load with LOAD CSV, batched in transactions of 5,000 rows"),
    ("neo4j/validation_queries.cypher", "Post-load counts and first fraud-footprint queries"),
    ("data/neo4j_import/import.sh", "Offline neo4j-admin bulk import command"),
    ("docker-compose.yml", "Neo4j 5.26 with APOC + Graph Data Science, both import mounts"),
] + [(f"data/neo4j_import/{r.file}", f"bulk-import {r.kind}: {r.name} ({r.rows:,} rows)") for r in manifest.itertuples()],
    columns=["file", "purpose"])
art["bytes"] = [(ROOT / f).stat().st_size for f in art.file]
art.to_csv(CFG.results_dir / "w1d3_artifact_manifest.csv", index=False)
print(art.to_string(index=False))

# %% [markdown]
# ## 2. Preview the generated Cypher

# %%
print((ROOT / "neo4j" / "constraints.cypher").read_text())
print((ROOT / "neo4j" / "load_csv.cypher").read_text()[:1900])

# %% [markdown]
# ## 3. Consistency checks (script vs schema vs data)
# Cheap, automatic checks that catch the usual mistakes before anyone starts a database.

# %%
cy = (ROOT / "neo4j" / "load_csv.cypher").read_text()
con = (ROOT / "neo4j" / "constraints.cypher").read_text()
checks = []
for label, s in SCHEMA["nodes"].items():
    csv = pd.read_csv(CFG.graph_dir / s["file"], nrows=5)
    checks.append((f"{label}: constraint exists", f"REQUIRE n.{s['key']} IS UNIQUE" in con))
    checks.append((f"{label}: CSV columns == schema properties", list(csv.columns) == list(s["props"])))
    checks.append((f"{label}: load statement present", f"CREATE (:{label} " in cy))
    keys = pd.read_csv(CFG.graph_dir / s["file"], usecols=[s["key"]])[s["key"]]
    checks.append((f"{label}: key unique in data", keys.is_unique))
for etype, e in SCHEMA["edges"].items():
    csv = pd.read_csv(CFG.graph_dir / e["file"], nrows=5)
    checks.append((f"{etype}: CSV columns == src_id, dst_id, props", list(csv.columns) == ["src_id", "dst_id", *e["props"]]))
    checks.append((f"{etype}: load statement present", f"-[:{etype}" in cy))
for r in manifest.itertuples():
    first = (CFG.neo4j_dir / r.file).read_text().splitlines()[0]
    ok = (":ID(" in first) if r.kind == "node" else (":START_ID(" in first and ":END_ID(" in first)
    checks.append((f"bulk header ok: {r.file}", ok))
chk = pd.DataFrame(checks, columns=["check", "passed"])
chk.to_csv(CFG.results_dir / "w1d3_consistency_checks.csv", index=False)
print(chk[~chk.passed].to_string(index=False) if (~chk.passed).any() else "all checks passed")
print(f"\n{int(chk.passed.sum())} of {len(chk)} checks passed")
assert chk.passed.all()

# %% [markdown]
# ## 4. Expected counts (what the database must contain after loading)

# %%
exp = pd.read_csv(CFG.results_dir / "w1d2_graph_counts.csv")[["kind", "label", "count"]]
exp.to_csv(CFG.results_dir / "w1d3_expected_counts.csv", index=False)
print(exp.to_string(index=False))
print("\nHow to run on your machine:\n  docker compose up -d\n  cat neo4j/constraints.cypher neo4j/load_csv.cypher | "
      "docker exec -i fraud-graph cypher-shell -u neo4j -p fraudgraph123\n  # or the fast offline route: see data/neo4j_import/import.sh")
