"""Generate Neo4j artefacts from the single SCHEMA definition (Week 1, Day 3).

Produces: constraints.cypher, indexes.cypher, load_csv.cypher (online load), bulk-import CSVs + import.sh (offline load),
docker-compose.yml, validation_queries.cypher. Targets Neo4j 5.x.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .transform import SCHEMA

CONV = {"STRING": "{v}", "INT64": "toInteger({v})", "DOUBLE": "toFloat({v})", "DATE": "date({v})",
        "TIMESTAMP": "datetime(replace({v}, ' ', 'T'))", "BOOLEAN": "({v} = 'True')"}
BULK = {"STRING": "", "INT64": ":long", "DOUBLE": ":double", "DATE": ":date", "TIMESTAMP": ":datetime", "BOOLEAN": ":boolean"}


def constraints() -> str:
    lines = ["// Uniqueness constraints (also create the lookup index for each key)"]
    for label, s in SCHEMA["nodes"].items():
        lines.append(f"CREATE CONSTRAINT {label.lower()}_{s['key']} IF NOT EXISTS "
                     f"FOR (n:{label}) REQUIRE n.{s['key']} IS UNIQUE;")
    return "\n".join(lines) + "\n"


def indexes() -> str:
    return "\n".join([
        "// Secondary indexes for the investigation queries used in Weeks 2-4",
        "CREATE INDEX account_external IF NOT EXISTS FOR (n:Account) ON (n.is_external);",
        "CREATE INDEX ip_vpn IF NOT EXISTS FOR (n:IPAddress) ON (n.is_vpn_proxy);",
        "CREATE INDEX user_city IF NOT EXISTS FOR (n:User) ON (n.city);",
        "CREATE INDEX transfer_ts IF NOT EXISTS FOR ()-[r:TRANSFERRED_TO]-() ON (r.ts);",
        "CREATE INDEX transfer_amount IF NOT EXISTS FOR ()-[r:TRANSFERRED_TO]-() ON (r.amount);", ""])


def load_csv(batch: int = 5000) -> str:
    out = ["// Online load. CSVs must be in Neo4j's import directory (docker-compose mounts data/graph there).",
           "// Run constraints.cypher FIRST, then this file with:  cypher-shell -f load_csv.cypher", ""]
    for label, s in SCHEMA["nodes"].items():
        props = ", ".join(f"{p}: " + CONV[t].format(v=f"row.{p}") for p, t in s["props"].items())
        out += [f"// ---- node {label}", f"LOAD CSV WITH HEADERS FROM 'file:///{s['file']}' AS row",
                f"CALL {{ WITH row CREATE (:{label} {{{props}}}) }} IN TRANSACTIONS OF {batch} ROWS;", ""]
    for etype, e in SCHEMA["edges"].items():
        sk, dk = SCHEMA["nodes"][e["src"]]["key"], SCHEMA["nodes"][e["dst"]]["key"]
        props = ", ".join(f"{p}: " + CONV[t].format(v=f"row.{p}") for p, t in e["props"].items())
        body = f" {{{props}}}" if props else ""
        out += [f"// ---- relationship {etype}", f"LOAD CSV WITH HEADERS FROM 'file:///{e['file']}' AS row",
                "CALL { WITH row",
                f"  MATCH (a:{e['src']} {{{sk}: row.src_id}}), (b:{e['dst']} {{{dk}: row.dst_id}})",
                f"  CREATE (a)-[:{etype}{body}]->(b)", f"}} IN TRANSACTIONS OF {batch} ROWS;", ""]
    return "\n".join(out)


def bulk_files(graph_dir: Path, out_dir: Path) -> pd.DataFrame:
    """Header-annotated CSVs for `neo4j-admin database import full` (fastest way to load, offline)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    def conv(df, props):
        df = df.copy()
        for p, t in props.items():
            if t == "BOOLEAN":
                df[p] = df[p].astype(str).str.lower()
            if t == "TIMESTAMP":
                df[p] = df[p].astype(str).str.replace(" ", "T") + "Z"
        return df

    for label, s in SCHEMA["nodes"].items():
        df = conv(pd.read_csv(graph_dir / s["file"]), s["props"])
        cols = {p: (f"{p}:ID({label})" if p == s["key"] else f"{p}{BULK[t]}") for p, t in s["props"].items()}
        df[list(cols)].rename(columns=cols).to_csv(out_dir / s["file"], index=False)
        rows.append(("node", label, s["file"], len(df)))
    for etype, e in SCHEMA["edges"].items():
        df = conv(pd.read_csv(graph_dir / e["file"]), e["props"])
        cols = {"src_id": f":START_ID({e['src']})", "dst_id": f":END_ID({e['dst']})",
                **{p: f"{p}{BULK[t]}" for p, t in e["props"].items()}}
        df[list(cols)].rename(columns=cols).to_csv(out_dir / e["file"], index=False)
        rows.append(("relationship", etype, e["file"], len(df)))
    return pd.DataFrame(rows, columns=["kind", "name", "file", "rows"])


def import_sh() -> str:
    nodes = " ".join(f"--nodes={l}=/bulk/{s['file']}" for l, s in SCHEMA["nodes"].items())
    rels = " ".join(f"--relationships={t}=/bulk/{e['file']}" for t, e in SCHEMA["edges"].items())
    return ("#!/usr/bin/env bash\n# Offline bulk import (stop the database first; use --overwrite-destination on a populated database).\n"
            "# Inside the container:  docker compose run --rm neo4j bash /bulk/import.sh\nset -e\n"
            f"neo4j-admin database import full neo4j --overwrite-destination=true \\\n  {nodes} \\\n  {rels}\n")


def compose() -> str:
    return """services:
  neo4j:
    image: neo4j:5.26-community
    container_name: fraud-graph
    ports:
      - "7474:7474"   # browser
      - "7687:7687"   # bolt
    environment:
      NEO4J_AUTH: neo4j/fraudgraph123
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
      NEO4J_server_memory_heap_max__size: 2G
      NEO4J_dbms_security_procedures_unrestricted: "gds.*,apoc.*"
    volumes:
      - ./data/graph:/var/lib/neo4j/import      # LOAD CSV source
      - ./data/neo4j_import:/bulk               # bulk-import files
      - neo4j_data:/data
volumes:
  neo4j_data:
"""


def validation_queries() -> str:
    return """// Run after loading. Expected counts are in results/w1d3_expected_counts.csv
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS nodes ORDER BY nodes DESC;
MATCH ()-[r]->() RETURN type(r) AS relationship, count(*) AS edges ORDER BY edges DESC;

// Users sharing a device with at least 2 other users (ring footprint)
MATCH (d:Device)<-[:USES_DEVICE]-(u:User)
WITH d, count(u) AS users WHERE users >= 3
RETURN d.device_id, users ORDER BY users DESC LIMIT 20;

// Identity documents used by more than one user (synthetic-identity footprint)
MATCH (i:IdentityDoc)<-[:HAS_ID_DOC]-(u:User)
WITH i, count(u) AS users WHERE users >= 2
RETURN i.id_doc_hash, users ORDER BY users DESC LIMIT 20;

// Money returning to its origin within 4 hops (circular flow preview)
MATCH p = (a:Account)-[:TRANSFERRED_TO*3..4]->(a)
RETURN a.account_id, length(p) AS hops LIMIT 20;
"""


def write_all(graph_dir: Path, neo4j_dir: Path, root: Path) -> pd.DataFrame:
    d = root / "neo4j"
    d.mkdir(parents=True, exist_ok=True)
    (d / "constraints.cypher").write_text(constraints())
    (d / "indexes.cypher").write_text(indexes())
    (d / "load_csv.cypher").write_text(load_csv())
    (d / "validation_queries.cypher").write_text(validation_queries())
    (root / "docker-compose.yml").write_text(compose())
    manifest = bulk_files(graph_dir, neo4j_dir)
    (neo4j_dir / "import.sh").write_text(import_sh())
    return manifest
