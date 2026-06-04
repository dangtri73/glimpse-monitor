create table if not exists devices (
  id text primary key,
  name text not null,
  role text not null,
  lan_ip inet,
  public_host text,
  health_path text,
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists services (
  id text primary key,
  device_id text references devices(id) on delete cascade,
  name text not null,
  process_pattern text not null,
  ports integer[] not null default '{}',
  actions_enabled boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists domain_gateway_targets (
  id text primary key,
  name text not null,
  target_device_id text references devices(id) on delete restrict,
  target_host text not null,
  target_port integer not null,
  protocol text not null check (protocol in ('http', 'https')),
  upstream text not null,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists port_mappings (
  id text primary key,
  name text not null,
  public_host text not null,
  public_port integer not null,
  target_id text references domain_gateway_targets(id) on delete restrict,
  target_device_id text references devices(id) on delete restrict,
  target_host text not null,
  target_port integer not null,
  upstream text,
  protocol text not null check (protocol in ('http', 'https', 'tcp')),
  status text not null check (status in ('draft', 'planned', 'active', 'disabled', 'failed')),
  auth_required boolean not null default true,
  verification_method text,
  verification_name text,
  verification_value text,
  verification_status text not null default 'pending' check (verification_status in ('pending', 'verified', 'failed')),
  verified_at timestamptz,
  applied_at timestamptz,
  rolled_back_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (public_host, public_port)
);

create table if not exists service_actions (
  id bigserial primary key,
  service_id text references services(id) on delete set null,
  action text not null check (action in ('start', 'stop', 'restart')),
  actor_user_id text,
  status text not null,
  stdout text,
  stderr text,
  created_at timestamptz not null default now()
);

create table if not exists audit_events (
  id bigserial primary key,
  actor_user_id text,
  event_type text not null,
  target_type text not null,
  target_id text,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists metric_samples (
  time timestamptz not null,
  device_id text not null references devices(id) on delete cascade,
  cpu_load_percent double precision not null,
  memory_used_percent double precision not null,
  disk_used_percent double precision not null,
  network_rx_bps double precision not null,
  network_tx_bps double precision not null,
  primary key (time, device_id)
);

create index if not exists metric_samples_device_time_idx
  on metric_samples (device_id, time desc);

create table if not exists network_interface_samples (
  time timestamptz not null,
  device_id text not null references devices(id) on delete cascade,
  interface_name text not null,
  rx_bytes bigint not null,
  tx_bytes bigint not null,
  primary key (time, device_id, interface_name)
);

create index if not exists network_interface_samples_device_time_idx
  on network_interface_samples (device_id, time desc);

-- If TimescaleDB is enabled:
-- select create_hypertable('metric_samples', 'time', if_not_exists => true);
-- select create_hypertable('network_interface_samples', 'time', if_not_exists => true);
