// Run after loading. Expected counts are in results/w1d3_expected_counts.csv
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
