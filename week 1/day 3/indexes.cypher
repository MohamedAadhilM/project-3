// Secondary indexes for the investigation queries used in Weeks 2-4
CREATE INDEX account_external IF NOT EXISTS FOR (n:Account) ON (n.is_external);
CREATE INDEX ip_vpn IF NOT EXISTS FOR (n:IPAddress) ON (n.is_vpn_proxy);
CREATE INDEX user_city IF NOT EXISTS FOR (n:User) ON (n.city);
CREATE INDEX transfer_ts IF NOT EXISTS FOR ()-[r:TRANSFERRED_TO]-() ON (r.ts);
CREATE INDEX transfer_amount IF NOT EXISTS FOR ()-[r:TRANSFERRED_TO]-() ON (r.amount);
