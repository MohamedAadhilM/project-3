"""Central configuration. Change values here, never inside the analysis code."""
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    seed: int = 2026
    n_legit_users: int = 6000
    n_rings: int = 12
    ring_size: tuple = (8, 14)
    n_external_accounts: int = 40
    n_communities: int = 40
    start: str = "2024-01-01"
    days: int = 366
    raw_dir: Path = field(default=ROOT / "data" / "raw")
    graph_dir: Path = field(default=ROOT / "data" / "graph")
    neo4j_dir: Path = field(default=ROOT / "data" / "neo4j_import")
    results_dir: Path = field(default=ROOT / "results")
    fig_dir: Path = field(default=ROOT / "reports" / "figures")
    report_dir: Path = field(default=ROOT / "reports")
    kuzu_path: Path = field(default=ROOT / "data" / "graph_db")

    def ensure(self):
        for p in (self.raw_dir, self.graph_dir, self.neo4j_dir, self.results_dir, self.fig_dir, self.report_dir):
            p.mkdir(parents=True, exist_ok=True)


CFG = Config()
