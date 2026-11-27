// Uniqueness constraints (also create the lookup index for each key)
CREATE CONSTRAINT user_user_id IF NOT EXISTS FOR (n:User) REQUIRE n.user_id IS UNIQUE;
CREATE CONSTRAINT account_account_id IF NOT EXISTS FOR (n:Account) REQUIRE n.account_id IS UNIQUE;
CREATE CONSTRAINT device_device_id IF NOT EXISTS FOR (n:Device) REQUIRE n.device_id IS UNIQUE;
CREATE CONSTRAINT ipaddress_ip_id IF NOT EXISTS FOR (n:IPAddress) REQUIRE n.ip_id IS UNIQUE;
CREATE CONSTRAINT phone_phone_hash IF NOT EXISTS FOR (n:Phone) REQUIRE n.phone_hash IS UNIQUE;
CREATE CONSTRAINT identitydoc_id_doc_hash IF NOT EXISTS FOR (n:IdentityDoc) REQUIRE n.id_doc_hash IS UNIQUE;
