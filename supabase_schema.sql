-- Run this in your Supabase SQL editor once to set up the table

create table if not exists runs (
  run_id       text primary key,
  repo         text,
  branch       text,
  workflow     text,
  outcome      text,          -- 'fixed' | 'escalated' | 'failed' | 'agent_error'
  confidence   float,
  reasoning    text,
  pr_url       text,
  error_type   text,
  timestamp    timestamptz default now()
);

-- Index for dashboard queries
create index if not exists runs_timestamp_idx on runs (timestamp desc);

-- Enable row-level security (optional but recommended)
alter table runs enable row level security;

-- Allow anon reads for the dashboard (tighten this for production)
create policy "allow_anon_read" on runs
  for select using (true);
