-- PostgreSQL schema for domens MVP
-- Focus: domain discovery, status tracking, Telegram alerts, confirmed registrations

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE domain_status AS ENUM (
  'unknown',
  'registered',
  'available',
  'pending_delete',
  'redemption',
  'client_hold',
  'inactive'
);

CREATE TYPE registration_status AS ENUM (
  'created',
  'queued',
  'sent_to_registrar',
  'registered',
  'failed',
  'canceled'
);

CREATE TABLE watchlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  owner_telegram_chat_id TEXT,
  auto_register BOOLEAN NOT NULL DEFAULT FALSE,
  max_price_usd NUMERIC(12,2),
  min_score NUMERIC(5,2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE domains (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fqdn TEXT NOT NULL UNIQUE,
  sld TEXT NOT NULL,
  tld TEXT NOT NULL,
  score NUMERIC(5,2),
  current_status domain_status NOT NULL DEFAULT 'unknown',
  status_checked_at TIMESTAMPTZ,
  drop_time_estimated_at TIMESTAMPTZ,
  source TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_domains_status_drop_time
  ON domains (current_status, drop_time_estimated_at);

CREATE TABLE watchlist_domains (
  watchlist_id UUID NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
  domain_id UUID NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
  priority SMALLINT NOT NULL DEFAULT 100,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (watchlist_id, domain_id)
);

CREATE TABLE domain_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  domain_id UUID NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
  status domain_status NOT NULL,
  provider TEXT,
  raw_payload JSONB,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_domain_status_history_domain_observed
  ON domain_status_history (domain_id, observed_at DESC);

CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  domain_id UUID NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
  watchlist_id UUID REFERENCES watchlists(id) ON DELETE SET NULL,
  telegram_chat_id TEXT NOT NULL,
  message_id TEXT,
  alert_type TEXT NOT NULL,
  confirmation_token TEXT UNIQUE,
  expires_at TIMESTAMPTZ,
  acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  acknowledged_at TIMESTAMPTZ
);

CREATE INDEX idx_alerts_token ON alerts (confirmation_token);
CREATE INDEX idx_alerts_unacked ON alerts (acknowledged, created_at DESC);

CREATE TABLE registrar_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider TEXT NOT NULL,
  account_name TEXT NOT NULL,
  api_base_url TEXT NOT NULL,
  api_key_ref TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(provider, account_name)
);

CREATE TABLE registration_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  domain_id UUID NOT NULL REFERENCES domains(id) ON DELETE RESTRICT,
  alert_id UUID REFERENCES alerts(id) ON DELETE SET NULL,
  registrar_account_id UUID REFERENCES registrar_accounts(id) ON DELETE SET NULL,
  requested_by TEXT,
  request_payload JSONB,
  response_payload JSONB,
  status registration_status NOT NULL DEFAULT 'created',
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX idx_registration_orders_status_created
  ON registration_orders (status, created_at DESC);
