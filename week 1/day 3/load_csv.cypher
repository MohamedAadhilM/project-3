// Online load. CSVs must be in Neo4j's import directory (docker-compose mounts data/graph there).
// Run constraints.cypher FIRST, then this file with:  cypher-shell -f load_csv.cypher

// ---- node User
LOAD CSV WITH HEADERS FROM 'file:///nodes_user.csv' AS row
CALL { WITH row CREATE (:User {user_id: row.user_id, full_name: row.full_name, email: row.email, dob: date(row.dob), signup_date: date(row.signup_date), city: row.city, kyc_level: toInteger(row.kyc_level)}) } IN TRANSACTIONS OF 5000 ROWS;

// ---- node Account
LOAD CSV WITH HEADERS FROM 'file:///nodes_account.csv' AS row
CALL { WITH row CREATE (:Account {account_id: row.account_id, bank_name: row.bank_name, account_type: row.account_type, opened_date: date(row.opened_date), status: row.status, is_external: (row.is_external = 'True')}) } IN TRANSACTIONS OF 5000 ROWS;

// ---- node Device
LOAD CSV WITH HEADERS FROM 'file:///nodes_device.csv' AS row
CALL { WITH row CREATE (:Device {device_id: row.device_id, device_type: row.device_type, os: row.os, fingerprint_hash: row.fingerprint_hash}) } IN TRANSACTIONS OF 5000 ROWS;

// ---- node IPAddress
LOAD CSV WITH HEADERS FROM 'file:///nodes_ip.csv' AS row
CALL { WITH row CREATE (:IPAddress {ip_id: row.ip_id, ip_address: row.ip_address, asn: row.asn, country: row.country, is_vpn_proxy: (row.is_vpn_proxy = 'True')}) } IN TRANSACTIONS OF 5000 ROWS;

// ---- node Phone
LOAD CSV WITH HEADERS FROM 'file:///nodes_phone.csv' AS row
CALL { WITH row CREATE (:Phone {phone_hash: row.phone_hash}) } IN TRANSACTIONS OF 5000 ROWS;

// ---- node IdentityDoc
LOAD CSV WITH HEADERS FROM 'file:///nodes_iddoc.csv' AS row
CALL { WITH row CREATE (:IdentityDoc {id_doc_hash: row.id_doc_hash}) } IN TRANSACTIONS OF 5000 ROWS;

// ---- relationship OWNS
LOAD CSV WITH HEADERS FROM 'file:///edges_owns.csv' AS row
CALL { WITH row
  MATCH (a:User {user_id: row.src_id}), (b:Account {account_id: row.dst_id})
  CREATE (a)-[:OWNS]->(b)
} IN TRANSACTIONS OF 5000 ROWS;

// ---- relationship USES_DEVICE
LOAD CSV WITH HEADERS FROM 'file:///edges_uses_device.csv' AS row
CALL { WITH row
  MATCH (a:User {user_id: row.src_id}), (b:Device {device_id: row.dst_id})
  CREATE (a)-[:USES_DEVICE {first_seen: date(row.first_seen), last_seen: date(row.last_seen), sessions: toInteger(row.sessions)}]->(b)
} IN TRANSACTIONS OF 5000 ROWS;

// ---- relationship LOGGED_IN_FROM
LOAD CSV WITH HEADERS FROM 'file:///edges_logged_in_from.csv' AS row
CALL { WITH row
  MATCH (a:User {user_id: row.src_id}), (b:IPAddress {ip_id: row.dst_id})
  CREATE (a)-[:LOGGED_IN_FROM {logins: toInteger(row.logins), first_login: date(row.first_login), last_login: date(row.last_login)}]->(b)
} IN TRANSACTIONS OF 5000 ROWS;

// ---- relationship HAS_PHONE
LOAD CSV WITH HEADERS FROM 'file:///edges_has_phone.csv' AS row
CALL { WITH row
  MATCH (a:User {user_id: row.src_id}), (b:Phone {phone_hash: row.dst_id})
  CREATE (a)-[:HAS_PHONE]->(b)
} IN TRANSACTIONS OF 5000 ROWS;

// ---- relationship HAS_ID_DOC
LOAD CSV WITH HEADERS FROM 'file:///edges_has_id_doc.csv' AS row
CALL { WITH row
  MATCH (a:User {user_id: row.src_id}), (b:IdentityDoc {id_doc_hash: row.dst_id})
  CREATE (a)-[:HAS_ID_DOC]->(b)
} IN TRANSACTIONS OF 5000 ROWS;

// ---- relationship TRANSFERRED_TO
LOAD CSV WITH HEADERS FROM 'file:///edges_transferred_to.csv' AS row
CALL { WITH row
  MATCH (a:Account {account_id: row.src_id}), (b:Account {account_id: row.dst_id})
  CREATE (a)-[:TRANSFERRED_TO {txn_id: row.txn_id, ts: datetime(replace(row.ts, ' ', 'T')), amount: toFloat(row.amount), currency: row.currency, channel: row.channel, status: row.status}]->(b)
} IN TRANSACTIONS OF 5000 ROWS;
