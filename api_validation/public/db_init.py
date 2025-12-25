import os
import psycopg

DDL = """
create table if not exists tenants (
  id uuid primary key,
  name text not null,
  status text not null default 'active',
  created_at timestamptz not null default now()
);

create table if not exists api_keys (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  key_prefix text not null unique,
  key_hash text not null,
  scopes text not null default '',
  status text not null default 'active',
  created_at timestamptz not null default now(),
  revoked_at timestamptz null,
  last_used_at timestamptz null
);

create table if not exists fixtures (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  storage_path text not null,
  sha256 text not null,
  size_bytes bigint not null,
  original_filename text not null,
  content_type text not null,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  deleted_at timestamptz null
);

create index if not exists idx_fixtures_tenant_id on fixtures(tenant_id);
create index if not exists idx_fixtures_tenant_status on fixtures(tenant_id, status);
"""

def init_db_if_enabled() -> None:
    # toggle so you can disable later without code changes
    if os.getenv("DB_INIT_ON_STARTUP", "1") != "1":
        return

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL not set")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
