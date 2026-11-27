#!/usr/bin/env bash
# Offline bulk import (stop the database first; use --overwrite-destination on a populated database).
# Inside the container:  docker compose run --rm neo4j bash /bulk/import.sh
set -e
neo4j-admin database import full neo4j --overwrite-destination=true \
  --nodes=User=/bulk/nodes_user.csv --nodes=Account=/bulk/nodes_account.csv --nodes=Device=/bulk/nodes_device.csv --nodes=IPAddress=/bulk/nodes_ip.csv --nodes=Phone=/bulk/nodes_phone.csv --nodes=IdentityDoc=/bulk/nodes_iddoc.csv \
  --relationships=OWNS=/bulk/edges_owns.csv --relationships=USES_DEVICE=/bulk/edges_uses_device.csv --relationships=LOGGED_IN_FROM=/bulk/edges_logged_in_from.csv --relationships=HAS_PHONE=/bulk/edges_has_phone.csv --relationships=HAS_ID_DOC=/bulk/edges_has_id_doc.csv --relationships=TRANSFERRED_TO=/bulk/edges_transferred_to.csv
