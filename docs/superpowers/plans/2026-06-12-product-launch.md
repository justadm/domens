# Product Launch Implementation Plan

Status: historical implementation plan. It is intentionally not the current checklist.

Use these current sources instead:
- `docs/product_backlog.md` for shipped state and remaining product work;
- `docs/product_launch_runbook.md` for canary and rollback;
- `docs/prod_checklist_idns.md` for production deploy and smoke checks.

Many checkbox items below were implemented after this plan was written, but the file was not maintained step-by-step. Do not treat unchecked boxes as current truth without verifying code and the current backlog.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Domens from a working MVP into a quiet, reliable, explainable Telegram-first domain radar suitable for a small production launch.

**Architecture:** Keep FastAPI as the source of truth for monitoring, scoring, Telegram, registration safety, and admin metrics. Make watchlists the primary product surface, move global monitoring to an explicit admin/demo mode, and add durable suppression/feedback so alerts become rare and useful.

**Tech Stack:** FastAPI, SQLAlchemy/PostgreSQL, Alembic, Vue 3/Vite/Pinia, Docker Compose, host nginx on MSK, Telegram Bot API, pytest, vue-tsc/Vite build.

---

## Launch Definition

The product is launch-ready when:

- Telegram `/start`, `/help`, `/profile`, `/watch`, `/alerts`, `/menu`, and callback buttons work reliably on stage.
- Monitoring is silent by default and never repeats the same domain to the same destination without a meaningful change.
- Each alert explains why it was sent.
- Users can configure personal watch rules and alert limits.
- Registration remains safe: disabled by default, fresh availability check before execution, explicit confirmation required.
- Admins can see alert volume, precision, duplicate suppression, Telegram delivery errors, and registration safety status.
- Deploy and rollback are documented and reproducible from the repository.

## File Structure Map

- `app/config.py` - add explicit launch-safe defaults and new monitoring/feedback knobs.
- `app/services/monitoring.py` - make monitoring watchlist-first, add suppression checks, include explanation payloads.
- `app/services/store.py` - add persistence models and methods for suppression, feedback, alert metrics, and readiness checks.
- `alembic/versions/0006_launch_quality.py` - add DB tables/columns for alert explanations, feedback, suppression, and metrics.
- `app/services/notifications.py` - add Telegram feedback buttons and delivery result logging.
- `app/routers/telegram.py` - handle alert feedback callbacks and improve `/help`, `/profile`, `/watch`, `/alerts`, `/menu` smoke reliability.
- `app/routers/cabinet.py` - expose user-facing alert history, watchlist limits, and explanation fields.
- `app/routers/admin.py` - expose readiness and product quality metrics.
- `frontend/src/pages/LkWatchPage.vue` - add watchlist controls for TLDs, max length, daily limit, and min score.
- `frontend/src/pages/LkAlertsPage.vue` - show alert explanations and feedback state.
- `frontend/src/pages/AdminDashboardPage.vue` - add launch readiness and alert quality panels.
- `tests/` - add focused tests for suppression, explanations, feedback, readiness, Telegram command delivery, and registration safety.
- `.github/workflows/deploy.yml` - add pre-deploy test/build gates.
- `docker-compose.yml`, `deploy/docker-compose.nginx.yml`, `deploy/docker-compose.frontend.override.yml` - make stage/prod compose reproducible with frontend included in the normal path.
- `docs/product_backlog.md`, `docs/prod_checklist_idns.md`, `docs/telegram_local_and_prod_runbook.md` - update launch/runbook details as behavior changes.

---

## Phase 1: Stabilize Stage And Telegram Delivery

### Task 1: Add Telegram Egress And Delivery Smoke Script

**Files:**
- Create: `scripts/smoke_telegram_stage.sh`
- Modify: `docs/telegram_local_and_prod_runbook.md`

- [ ] **Step 1: Create the smoke script**

Create `scripts/smoke_telegram_stage.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/domens}"
ADMIN_CHAT_ID="${ADMIN_CHAT_ID:-}"

cd "$APP_DIR"

token="$(awk -F= '$1=="TELEGRAM_BOT_TOKEN"{print $2; exit}' .env)"
webhook_url="$(awk -F= '$1=="WEBHOOK_URL"{print $2; exit}' .env)"

if [[ -z "$token" ]]; then
  echo "TELEGRAM_BOT_TOKEN is missing"
  exit 1
fi

echo "== Host Telegram API =="
curl -4 -fsS --max-time 15 "https://api.telegram.org/bot${token}/getMe" >/dev/null
echo "host_getMe=ok"

echo "== Container Telegram TCP =="
docker exec domens-api-1 python -c 'import socket; s=socket.create_connection(("api.telegram.org",443),15); s.close(); print("container_tcp=ok")'

echo "== Webhook info =="
curl -4 -fsS --max-time 15 "https://api.telegram.org/bot${token}/getWebhookInfo"
echo

if [[ -n "$webhook_url" ]]; then
  echo "== Backend webhook endpoint =="
  curl -fsS -X POST "$webhook_url" -H 'Content-Type: application/json' -d '{}' >/dev/null
  echo "backend_webhook=ok"
fi

if [[ -n "$ADMIN_CHAT_ID" ]]; then
  echo "== Send message =="
  curl -4 -fsS --max-time 15 \
    "https://api.telegram.org/bot${token}/sendMessage" \
    -H 'Content-Type: application/json' \
    -d "{\"chat_id\":\"${ADMIN_CHAT_ID}\",\"text\":\"Domens Telegram smoke OK\"}" >/dev/null
  echo "sendMessage=ok"
fi
```

- [ ] **Step 2: Make it executable**

Run:

```bash
chmod +x scripts/smoke_telegram_stage.sh
```

- [ ] **Step 3: Document stage usage**

Add to `docs/telegram_local_and_prod_runbook.md`:

````markdown
## Stage smoke after routing changes

Run on MSK:

```bash
cd /opt/domens
ADMIN_CHAT_ID=<admin_chat_id> ./scripts/smoke_telegram_stage.sh
```

Expected:
- host `getMe` succeeds;
- `domens-api-1` can open TCP to `api.telegram.org:443`;
- webhook URL matches the chosen delivery mode: empty for polling, `https://idns.devee.ru/v1/telegram/webhook` for webhook;
- optional admin `sendMessage` succeeds.
````

- [ ] **Step 4: Verify**

Run locally:

```bash
bash -n scripts/smoke_telegram_stage.sh
```

Expected: exit code `0`.

Run on stage after deploy:

```bash
ssh msk 'cd /opt/domens && ADMIN_CHAT_ID=13903713 ./scripts/smoke_telegram_stage.sh'
```

Expected: all checks print `ok`.

### Task 2: Add Telegram Command And Menu Regression Tests

**Files:**
- Modify: `tests/test_telegram_admin_commands.py`
- Modify: `app/routers/telegram.py`

- [ ] **Step 1: Add tests for `/help`, `/profile`, and `/menu` responses**

Add tests that assert commands log events and call `send_telegram_message` or `send_telegram_text`.

```python
def test_telegram_help_replies(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []

    async def fake_send(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        sent.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr("app.routers.telegram.send_telegram_message", fake_send)

    response = client.post(
        "/v1/telegram/webhook",
        json={
            "message": {
                "text": "/help",
                "chat": {"id": 13903713},
                "from": {"id": 13903713, "username": "just", "first_name": "Just"},
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert sent
    assert sent[0][0] == "13903713"
    assert "/watch" in sent[0][1]


def test_telegram_profile_replies(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []

    async def fake_send(chat_id: str, text: str) -> dict:
        sent.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr("app.routers.telegram.send_telegram_text", fake_send)

    response = client.post(
        "/v1/telegram/webhook",
        json={
            "message": {
                "text": "/profile",
                "chat": {"id": 13903713},
                "from": {"id": 13903713, "username": "just", "first_name": "Just"},
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert sent
    assert "13903713" in sent[0][1]


def test_telegram_menu_replies_with_main_actions(monkeypatch) -> None:
    sent: list[tuple[str, str, dict | None]] = []

    async def fake_send(chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        sent.append((chat_id, text, reply_markup))
        return {"ok": True}

    monkeypatch.setattr("app.routers.telegram.send_telegram_message", fake_send)

    response = client.post(
        "/v1/telegram/webhook",
        json={
            "message": {
                "text": "/menu",
                "chat": {"id": 13903713},
                "from": {"id": 13903713, "username": "just", "first_name": "Just"},
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert sent
    assert "watch" in sent[0][1].lower() or "прав" in sent[0][1].lower()
    assert sent[0][2] is not None
```

- [ ] **Step 2: Run tests**

Run:

```bash
.venv313/bin/pytest tests/test_telegram_admin_commands.py -q
```

Expected: tests pass. If they fail because existing helpers use `send_telegram_text` instead of `send_telegram_message`, adjust the monkeypatch target to the actual function used by the command handler.

- [ ] **Step 3: Stage smoke**

After routing is confirmed, send `/help`, `/profile`, and `/menu` from Telegram and verify:

```bash
ssh msk 'docker exec -i domens-postgres-1 psql -U domens -d domens -c "select created_at,event_type,telegram_chat_id,payload from bot_events order by created_at desc limit 10;"'
```

Expected: fresh `incoming_message`, `command_help`, `command_profile`, and `command_menu` rows.

### Task 3: Decide And Document Telegram Delivery Mode

**Files:**
- Modify: `docs/telegram_local_and_prod_runbook.md`
- Modify: `docs/prod_checklist_idns.md`

- [ ] **Step 1: Record current stage mode**

Add to `docs/telegram_local_and_prod_runbook.md`:

```markdown
## Current stage delivery mode

As of 2026-06-12, MSK stage uses Telegram polling:

- `TELEGRAM_POLLING_ENABLED=true`
- Telegram webhook URL is empty
- `/help`, `/profile`, and `/watch list` are observed in `bot_events`

Before product launch, choose one production mode:
- polling: simpler behind custom routing, webhook stays empty;
- webhook: lower idle API traffic, requires stable public Telegram delivery to `https://idns.devee.ru/v1/telegram/webhook`.
```

- [ ] **Step 2: Update prod checklist**

In `docs/prod_checklist_idns.md`, replace the hardcoded webhook-only assumption with:

```markdown
Choose Telegram delivery mode before launch:
- Polling mode: `TELEGRAM_POLLING_ENABLED=true`, webhook URL empty.
- Webhook mode: `TELEGRAM_POLLING_ENABLED=false`, webhook URL set to `https://idns.devee.ru/v1/telegram/webhook`.
```

- [ ] **Step 3: Verify stage mode**

Run:

```bash
ssh msk 'docker exec domens-api-1 env | awk -F= '\''/^(TELEGRAM_POLLING_ENABLED|WEBHOOK_URL)=/ {print}'\'''
ssh msk 'cd /opt/domens && TOKEN=$(awk -F= '\''$1=="TELEGRAM_BOT_TOKEN"{print $2; exit}'\'' .env) && curl -4 -fsS --max-time 15 "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"'
```

Expected: either polling is true and webhook URL is empty, or polling is false and webhook URL is `https://idns.devee.ru/v1/telegram/webhook`.

---

## Phase 2: Make Deploy Reproducible

### Task 4: Make Frontend Part Of The Standard Compose Path

**Files:**
- Modify: `docker-compose.yml`
- Modify: `deploy/docker-compose.nginx.yml`
- Modify: `deploy/docker-compose.frontend.override.yml`
- Modify: `docs/prod_checklist_idns.md`

- [ ] **Step 1: Move frontend service into `docker-compose.yml`**

Add a `frontend` service:

```yaml
  frontend:
    build:
      context: .
      dockerfile: deploy/frontend.Dockerfile
    ports:
      - "127.0.0.1:28200:80"
    restart: unless-stopped
```

- [ ] **Step 2: Keep override as compatibility shim**

Replace `deploy/docker-compose.frontend.override.yml` with:

```yaml
services:
  frontend:
    build:
      context: ..
      dockerfile: deploy/frontend.Dockerfile
```

- [ ] **Step 3: Validate compose**

Run:

```bash
docker compose config --services
docker compose -f deploy/docker-compose.nginx.yml config --services
```

Expected: `api`, `postgres`, `redis`, and `frontend` appear in the intended stage/prod command path.

- [ ] **Step 4: Update docs**

In `docs/prod_checklist_idns.md`, replace first run with:

```bash
cd /opt/domens
sudo -n docker compose -p domens -f docker-compose.yml up -d --build
sudo -n docker compose -p domens -f docker-compose.yml ps
```

Keep the note that host nginx routes backend to `28080` and frontend to `28200`.

### Task 5: Add Pre-Deploy CI Gates

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: Add backend test step before deploy**

Insert before SSH deploy:

```yaml
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install backend dependencies
        run: pip install -r requirements.txt

      - name: Run backend tests
        run: pytest -q
```

- [ ] **Step 2: Add frontend build step**

Insert before SSH deploy:

```yaml
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Build frontend
        working-directory: frontend
        run: |
          npm ci
          npm run build
```

- [ ] **Step 3: Add compose config validation**

Insert before SSH deploy:

```yaml
      - name: Validate compose
        run: docker compose config >/dev/null
```

- [ ] **Step 4: Verify locally**

Run:

```bash
.venv313/bin/pytest -q
cd frontend && npm run build
cd .. && docker compose config >/dev/null
```

Expected: all commands exit `0`.

---

## Phase 3: Readiness And Safe Defaults

### Task 6: Add Real Readiness Endpoint

**Files:**
- Modify: `app/main.py`
- Modify: `app/schemas.py`
- Modify: `app/services/store.py`
- Test: `tests/test_readiness.py`

- [ ] **Step 1: Add schema**

Add to `app/schemas.py`:

```python
class ReadinessResponse(BaseModel):
    status: str
    database: bool
    telegram_configured: bool
    monitoring_enabled: bool
    registration_enabled: bool
```

- [ ] **Step 2: Add store ping**

Add to `PostgresStore` in `app/services/store.py`:

```python
    def ping(self) -> bool:
        try:
            with self._session() as session:
                session.execute(select(1))
            return True
        except Exception:
            return False
```

- [ ] **Step 3: Add route**

Add to `app/main.py`:

```python
@app.get("/ready", response_model=ReadinessResponse)
async def ready() -> ReadinessResponse:
    database_ok = store.ping()
    return ReadinessResponse(
        status="ok" if database_ok else "degraded",
        database=database_ok,
        telegram_configured=bool(settings.telegram_bot_token and settings.telegram_bot_username),
        monitoring_enabled=bool(settings.monitor_enabled),
        registration_enabled=bool(settings.registration_enabled),
    )
```

- [ ] **Step 4: Write tests**

Create `tests/test_readiness.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ready_returns_runtime_flags(monkeypatch) -> None:
    monkeypatch.setattr("app.main.store.ping", lambda: True)
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] is True
    assert "monitoring_enabled" in data
    assert "registration_enabled" in data
```

- [ ] **Step 5: Verify**

Run:

```bash
.venv313/bin/pytest tests/test_readiness.py -q
```

Expected: pass.

### Task 7: Make Stage/Prod Monitoring Explicitly Safe

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example`
- Modify: `docs/prod_checklist_idns.md`
- Test: `tests/test_config_defaults.py`

- [ ] **Step 1: Change default**

In `app/config.py`, set:

```python
monitor_enabled: bool = False
```

- [ ] **Step 2: Update `.env.example`**

Set:

```dotenv
MONITOR_ENABLED=false
MONITOR_ALERT_GLOBAL_RUN_LIMIT=3
MONITOR_ALERT_PER_TARGET_RUN_LIMIT=1
MONITOR_ALERT_PER_TARGET_DAILY_LIMIT=3
MONITOR_ALERT_COOLDOWN_MINUTES=1440
```

- [ ] **Step 3: Add config test**

Create `tests/test_config_defaults.py`:

```python
from app.config import Settings


def test_monitoring_is_off_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.monitor_enabled is False
    assert settings.registration_enabled is False
```

- [ ] **Step 4: Verify**

Run:

```bash
.venv313/bin/pytest tests/test_config_defaults.py -q
```

Expected: pass.

---

## Phase 4: Quiet Radar And Duplicate Suppression

### Task 8: Add Persistent Alert Suppression

**Files:**
- Create: `alembic/versions/0006_launch_quality.py`
- Modify: `app/services/store.py`
- Modify: `app/services/monitoring.py`
- Test: `tests/test_alert_suppression.py`

- [ ] **Step 1: Add migration**

Create `alembic/versions/0006_launch_quality.py`:

```python
"""launch quality tracking

Revision ID: 0006_launch_quality
Revises: 0005_copilot_logging
Create Date: 2026-06-12
"""

from alembic import op


revision = "0006_launch_quality"
down_revision = "0005_copilot_logging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE alerts
        ADD COLUMN IF NOT EXISTS explanation JSONB,
        ADD COLUMN IF NOT EXISTS delivery_payload JSONB
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_feedback (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          alert_id UUID REFERENCES alerts(id) ON DELETE CASCADE,
          telegram_user_id TEXT,
          feedback_type TEXT NOT NULL,
          payload JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_alert_feedback_alert ON alert_feedback(alert_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alert_feedback_user ON alert_feedback(telegram_user_id, created_at DESC)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_suppressions (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          fqdn TEXT NOT NULL,
          destination TEXT NOT NULL,
          reason TEXT NOT NULL,
          status TEXT,
          score NUMERIC(5,2),
          expires_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(fqdn, destination, reason)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_alert_suppressions_lookup ON alert_suppressions(fqdn, destination, expires_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alert_suppressions CASCADE")
    op.execute("DROP TABLE IF EXISTS alert_feedback CASCADE")
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS delivery_payload")
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS explanation")
```

- [ ] **Step 2: Add ORM models**

Add to `app/services/store.py` near the other SQLAlchemy models:

```python
class AlertFeedbackModel(Base):
    __tablename__ = "alert_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=False)
    telegram_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class AlertSuppressionModel(Base):
    __tablename__ = "alert_suppressions"
    __table_args__ = (UniqueConstraint("fqdn", "destination", "reason", name="uq_alert_suppressions_target_reason"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fqdn: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 3: Add store methods**

Add methods to `PostgresStore`:

```python
    def should_suppress_alert(self, fqdn: str, destination: str, reason: str) -> bool:
        now = datetime.now(timezone.utc)
        with self._session() as session:
            row = session.execute(
                select(AlertSuppressionModel)
                .where(AlertSuppressionModel.fqdn == fqdn.strip().lower())
                .where(AlertSuppressionModel.destination == str(destination))
                .where(AlertSuppressionModel.reason == reason)
                .where(or_(AlertSuppressionModel.expires_at.is_(None), AlertSuppressionModel.expires_at > now))
                .limit(1)
            ).scalar_one_or_none()
            return row is not None

    def suppress_alert(self, fqdn: str, destination: str, reason: str, days: int = 30) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, days))
        with self._session() as session:
            existing = session.execute(
                select(AlertSuppressionModel)
                .where(AlertSuppressionModel.fqdn == fqdn.strip().lower())
                .where(AlertSuppressionModel.destination == str(destination))
                .where(AlertSuppressionModel.reason == reason)
                .limit(1)
            ).scalar_one_or_none()
            if existing:
                existing.expires_at = expires_at
            else:
                session.add(
                    AlertSuppressionModel(
                        fqdn=fqdn.strip().lower(),
                        destination=str(destination),
                        reason=reason,
                        expires_at=expires_at,
                    )
                )
            session.commit()
```

- [ ] **Step 4: Use suppression in monitoring**

Before creating any alert in `app/services/monitoring.py`, check:

```python
if self.store.should_suppress_alert(fqdn, destination, reason="same_domain"):
    return
```

After sending or recording an alert:

```python
self.store.suppress_alert(fqdn, destination, reason="same_domain", days=30)
```

- [ ] **Step 5: Add tests**

Create `tests/test_alert_suppression.py` with store-level tests for:

```python
def test_same_domain_destination_is_suppressed_after_first_alert(store) -> None:
    assert store.should_suppress_alert("stackai.ru", "13903713", "same_domain") is False
    store.suppress_alert("stackai.ru", "13903713", "same_domain", days=30)
    assert store.should_suppress_alert("stackai.ru", "13903713", "same_domain") is True
```

- [ ] **Step 6: Verify**

Run:

```bash
.venv313/bin/pytest tests/test_alert_suppression.py tests/test_registration_safety.py -q
```

Expected: pass.

### Task 9: Add Alert Explanation Payloads

**Files:**
- Modify: `app/services/monitoring.py`
- Modify: `app/services/store.py`
- Modify: `app/services/notifications.py`
- Test: `tests/test_alert_explanations.py`

- [ ] **Step 1: Define explanation shape**

Use this JSON shape in `alerts.explanation`:

```json
{
  "score": 87.5,
  "status": "available",
  "provider": "timeweb",
  "matched_query": "ai tools",
  "tld": "ru",
  "length": 7,
  "risk": "provider_check_required",
  "checked_at": "2026-06-12T15:00:00Z"
}
```

- [ ] **Step 2: Extend `create_alert`**

Update `PostgresStore.create_alert` signature:

```python
def create_alert(
    self,
    domain: str,
    telegram_chat_id: str,
    token: str,
    alert_type: str = "manual_trigger",
    explanation: dict | None = None,
) -> Alert:
```

Save `explanation=explanation or {}` in `AlertModel`.

- [ ] **Step 3: Build explanation in monitoring**

Add helper:

```python
def _build_alert_explanation(self, fqdn: str, status: str, score: float, provider: str, matched_query: str | None) -> dict:
    name, _, tld = fqdn.partition(".")
    return {
        "score": round(float(score), 2),
        "status": status,
        "provider": provider,
        "matched_query": matched_query,
        "tld": tld,
        "length": len(name),
        "risk": "provider_check_required" if provider == "heuristic" else "provider_checked",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: Include explanation in Telegram text**

Update `send_telegram_alert` to accept `explanation: dict | None = None` and append:

```python
details = ""
if explanation:
    details = (
        f"\n\nScore: {explanation.get('score')}"
        f"\nStatus: {explanation.get('status')}"
        f"\nTLD: .{explanation.get('tld')}"
    )
```

- [ ] **Step 5: Test**

Create `tests/test_alert_explanations.py`:

```python
def test_alert_explanation_contains_score_status_and_tld() -> None:
    explanation = monitoring_service._build_alert_explanation(
        fqdn="stackai.ru",
        status="available",
        score=87.345,
        provider="timeweb",
        matched_query="ai tools",
    )
    assert explanation["score"] == 87.34 or explanation["score"] == 87.35
    assert explanation["status"] == "available"
    assert explanation["tld"] == "ru"
    assert explanation["matched_query"] == "ai tools"
```

- [ ] **Step 6: Verify**

Run:

```bash
.venv313/bin/pytest tests/test_alert_explanations.py -q
```

Expected: pass.

---

## Phase 5: Feedback Loop

### Task 10: Add Telegram Feedback Buttons

**Files:**
- Modify: `app/services/notifications.py`
- Modify: `app/routers/telegram.py`
- Modify: `app/services/store.py`
- Test: `tests/test_alert_feedback.py`

- [ ] **Step 1: Add buttons to alert keyboard**

In `send_telegram_alert`, extend inline keyboard:

```python
[
    {"text": "Больше таких", "callback_data": f"feedback:more:{token}"},
    {"text": "Меньше таких", "callback_data": f"feedback:less:{token}"},
],
[
    {"text": "Не повторять", "callback_data": f"feedback:never:{token}"},
]
```

- [ ] **Step 2: Add store method**

Add:

```python
def record_alert_feedback(self, token: str, telegram_user_id: str, feedback_type: str, payload: dict | None = None) -> bool:
    with self._session() as session:
        alert = session.execute(
            select(AlertModel).where(AlertModel.confirmation_token == token).limit(1)
        ).scalar_one_or_none()
        if not alert:
            return False
        session.add(
            AlertFeedbackModel(
                alert_id=alert.id,
                telegram_user_id=str(telegram_user_id),
                feedback_type=feedback_type,
                payload=payload or {},
            )
        )
        session.commit()
        return True
```

- [ ] **Step 3: Handle callback**

In `app/routers/telegram.py`, before register/skip callback handling:

```python
if callback_data.startswith("feedback:"):
    _, feedback_type, token = callback_data.split(":", 2)
    ok = store.record_alert_feedback(token, from_user_id, feedback_type)
    if feedback_type == "never":
        alert = store.get_alert_by_token(token)
        if alert:
            store.suppress_alert(alert.domain, alert.telegram_chat_id, reason="user_never", days=365)
    if callback_query_id:
        await answer_telegram_callback(callback_query_id, "Принято")
    return {"ok": ok, "action": "feedback", "feedback_type": feedback_type}
```

- [ ] **Step 4: Test**

Create `tests/test_alert_feedback.py` with:

```python
def test_feedback_callback_is_recorded(monkeypatch) -> None:
    recorded = {}
    monkeypatch.setattr(
        telegram_router.store,
        "record_alert_feedback",
        lambda token, telegram_user_id, feedback_type, payload=None: recorded.update(
            {"token": token, "user": telegram_user_id, "type": feedback_type}
        ) or True,
    )

    response = client.post(
        "/v1/telegram/webhook",
        json={
            "callback_query": {
                "id": "cb1",
                "data": "feedback:less:cfm_123",
                "from": {"id": 13903713},
                "message": {"chat": {"id": 13903713}},
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["action"] == "feedback"
    assert recorded == {"token": "cfm_123", "user": "13903713", "type": "less"}
```

- [ ] **Step 5: Verify**

Run:

```bash
.venv313/bin/pytest tests/test_alert_feedback.py tests/test_telegram_admin_commands.py -q
```

Expected: pass.

---

## Phase 6: Watchlist-First Product Surface

### Task 11: Add User Alert Limits To Watch Rules

**Files:**
- Modify: `app/services/store.py`
- Modify: `app/routers/cabinet.py`
- Modify: `frontend/src/pages/LkWatchPage.vue`
- Create: `alembic/versions/0007_watch_rule_limits.py`
- Test: `tests/test_cabinet_watch_limits.py`

- [ ] **Step 1: Add columns**

Create migration:

```python
"""watch rule alert limits

Revision ID: 0007_watch_rule_limits
Revises: 0006_launch_quality
Create Date: 2026-06-12
"""

from alembic import op


revision = "0007_watch_rule_limits"
down_revision = "0006_launch_quality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_watch_rules ADD COLUMN IF NOT EXISTS max_length INTEGER")
    op.execute("ALTER TABLE user_watch_rules ADD COLUMN IF NOT EXISTS daily_alert_limit INTEGER NOT NULL DEFAULT 3")


def downgrade() -> None:
    op.execute("ALTER TABLE user_watch_rules DROP COLUMN IF EXISTS daily_alert_limit")
    op.execute("ALTER TABLE user_watch_rules DROP COLUMN IF EXISTS max_length")
```

- [ ] **Step 2: Extend API request/response models**

In `app/routers/cabinet.py`, add fields:

```python
max_length: int | None = None
daily_alert_limit: int = 3
```

Validate:

```python
safe_daily_limit = max(1, min(int(payload.daily_alert_limit or 3), 10))
safe_max_length = None if payload.max_length is None else max(3, min(int(payload.max_length), 30))
```

- [ ] **Step 3: Apply limits in monitoring**

When evaluating watch targets:

```python
max_length = target.get("max_length")
if max_length is not None and len(fqdn.split(".", 1)[0]) > int(max_length):
    continue
```

Use `daily_alert_limit` instead of the global default for that watch target.

- [ ] **Step 4: Update Vue form**

Add controls in `frontend/src/pages/LkWatchPage.vue`:

```vue
<input v-model.trim="createForm.max_length" type="number" min="3" max="30" placeholder="Max length" />
<input v-model.trim="createForm.daily_alert_limit" type="number" min="1" max="10" placeholder="Daily alerts" />
```

Send fields in the create/update payload.

- [ ] **Step 5: Test**

Create `tests/test_cabinet_watch_limits.py`:

```python
def test_watch_rule_limits_are_clamped(client, monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(cabinet_router.store, "add_watch_rule", lambda **kwargs: captured.update(kwargs) or "rule-1")

    response = client.post(
        "/v1/cabinet/watch-rules",
        json={"query": "ai tools", "daily_alert_limit": 99, "max_length": 100},
    )

    assert response.status_code == 200
    assert captured["daily_alert_limit"] == 10
    assert captured["max_length"] == 30
```

- [ ] **Step 6: Verify**

Run:

```bash
.venv313/bin/pytest tests/test_cabinet_watch_limits.py -q
cd frontend && npm run build
```

Expected: pass and build succeeds.

---

## Phase 7: Registration Trust And Safety

### Task 12: Strengthen Fresh Availability Check

**Files:**
- Modify: `app/routers/registrations.py`
- Modify: `app/services/store.py`
- Test: `tests/test_registration_safety.py`

- [ ] **Step 1: Persist provider check time**

Ensure registration execution records:

```python
{
    "availability_check": {
        "provider": result.get("provider"),
        "available": result.get("available"),
        "status": result.get("status"),
        "checked_at": datetime.now(timezone.utc).isoformat()
    }
}
```

- [ ] **Step 2: Block unknown availability**

In registration execution:

```python
if settings.registration_require_available_check:
    availability = await registrar_client.check_availability(order.domain)
    if availability.get("available") is not True:
        store.mark_order_failed(order_id, "fresh availability check failed", response_payload=availability)
        return ExecuteRegistrationResponse(
            order_id=order_id,
            status="failed",
            registrar_response={"error": "fresh availability check failed", "availability": availability},
        )
```

- [ ] **Step 3: Test**

Extend `tests/test_registration_safety.py`:

```python
def test_execute_blocks_unknown_availability(monkeypatch) -> None:
    async def fake_check(_domain: str) -> dict:
        return {"provider": "timeweb", "available": None, "status": "unknown"}

    monkeypatch.setattr(registrations.registrar_client, "check_availability", fake_check)
    response = client.post("/v1/registrations/order-1/execute")
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
```

- [ ] **Step 4: Verify**

Run:

```bash
.venv313/bin/pytest tests/test_registration_safety.py -q
```

Expected: pass.

---

## Phase 8: Product Quality Metrics

### Task 13: Add Admin Quality Dashboard API

**Files:**
- Modify: `app/services/store.py`
- Modify: `app/routers/admin.py`
- Modify: `frontend/src/pages/AdminDashboardPage.vue`
- Test: `tests/test_admin_quality_metrics.py`

- [ ] **Step 1: Add store aggregation**

Add method:

```python
def get_alert_quality_metrics(self, days: int = 7) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    with self._session() as session:
        alerts_total = int(session.execute(select(func.count()).select_from(AlertModel).where(AlertModel.created_at >= since)).scalar() or 0)
        feedback_total = int(session.execute(select(func.count()).select_from(AlertFeedbackModel).where(AlertFeedbackModel.created_at >= since)).scalar() or 0)
        suppressed_total = int(session.execute(select(func.count()).select_from(AlertSuppressionModel).where(AlertSuppressionModel.created_at >= since)).scalar() or 0)
        return {
            "days": days,
            "alerts_total": alerts_total,
            "feedback_total": feedback_total,
            "suppressed_total": suppressed_total,
        }
```

- [ ] **Step 2: Add admin route**

In `app/routers/admin.py`:

```python
@router.get("/quality")
async def admin_quality(request: Request, days: int = 7) -> dict:
    _require_admin(request)
    return store.get_alert_quality_metrics(days=days)
```

- [ ] **Step 3: Add frontend panel**

In `AdminDashboardPage.vue`, fetch `/v1/admin/quality?days=7` and render:

```vue
<article class="kpi"><p>Alerts 7d</p><h3>{{ quality.alerts_total }}</h3></article>
<article class="kpi"><p>Feedback 7d</p><h3>{{ quality.feedback_total }}</h3></article>
<article class="kpi"><p>Suppressed 7d</p><h3>{{ quality.suppressed_total }}</h3></article>
```

- [ ] **Step 4: Test**

Create `tests/test_admin_quality_metrics.py`:

```python
def test_admin_quality_endpoint_returns_metrics(monkeypatch) -> None:
    monkeypatch.setattr(admin_router.store, "get_alert_quality_metrics", lambda days=7: {
        "days": days,
        "alerts_total": 2,
        "feedback_total": 1,
        "suppressed_total": 3,
    })
    response = client.get("/v1/admin/quality?days=7")
    assert response.status_code == 200
    assert response.json()["alerts_total"] == 2
```

- [ ] **Step 5: Verify**

Run:

```bash
.venv313/bin/pytest tests/test_admin_quality_metrics.py -q
cd frontend && npm run build
```

Expected: pass and build succeeds.

---

## Phase 9: Launch Runbook And Canary

### Task 14: Write Product Launch Runbook

**Files:**
- Create: `docs/product_launch_runbook.md`
- Modify: `docs/prod_checklist_idns.md`

- [ ] **Step 1: Create runbook**

Create `docs/product_launch_runbook.md`:

```markdown
# Product launch runbook

## Pre-launch gates

- Backend tests pass: `.venv313/bin/pytest -q`
- Frontend build passes: `cd frontend && npm run build`
- Compose config is valid: `docker compose config >/dev/null`
- `/ready` returns `database=true`
- Telegram smoke script passes on MSK
- `MONITOR_ENABLED=false` until canary watchlist is configured
- `REGISTRATION_ENABLED=false` until manual approval

## Canary setup

1. Enable one admin watchlist.
2. Set daily alert limit to `1`.
3. Keep global monitoring disabled.
4. Observe 24 hours.
5. Confirm:
   - no repeated same-domain spam;
   - alerts include explanation;
   - feedback callbacks work;
   - `/help` and `/profile` work;
   - quality metrics are visible.

## Rollback

1. Set `MONITOR_ENABLED=false`.
2. Recreate API service.
3. Confirm `/ready` and `/health`.
4. Keep frontend running unless UI itself is the incident source.
```

- [ ] **Step 2: Link from prod checklist**

Add to `docs/prod_checklist_idns.md`:

```markdown
Before enabling monitoring or registration, follow `docs/product_launch_runbook.md`.
```

- [ ] **Step 3: Verify**

Run:

```bash
rg -n "product_launch_runbook|MONITOR_ENABLED=false|REGISTRATION_ENABLED=false" docs
```

Expected: references appear in both runbook and checklist.

---

## Recommended Execution Order

1. Phase 1: Telegram smoke and command reliability.
2. Phase 2: reproducible compose/deploy.
3. Phase 3: readiness endpoint and safe defaults.
4. Phase 4: duplicate suppression and explanations.
5. Phase 5: Telegram feedback.
6. Phase 6: watchlist-first limits.
7. Phase 7: registration safety.
8. Phase 8: admin metrics.
9. Phase 9: launch runbook and canary.

## Verification Before Product Launch

Run locally:

```bash
.venv313/bin/pytest -q
cd frontend && npm run build
cd .. && docker compose config >/dev/null
```

Run on stage:

```bash
ssh msk 'cd /opt/domens && ./scripts/smoke_telegram_stage.sh'
ssh msk 'curl -fsS http://127.0.0.1:28080/ready'
ssh msk 'curl -fsS https://idns.devee.ru/'
ssh msk 'curl -fsS https://idns.devee.ru/health'
```

Manual stage checks:

- Send `/help` in Telegram and verify a reply.
- Send `/profile` in Telegram and verify a reply.
- Create one watch rule for admin user.
- Re-enable monitoring only for the canary.
- Confirm at most one alert in 24 hours for the canary.
- Press a feedback button and verify it is stored.

## Self-Review

- Spec coverage: every item from `docs/product_backlog.md` maps to a task in this plan.
- Placeholder scan: no unfinished placeholders or intentionally vague implementation steps remain.
- Type consistency: new concepts use consistent names: `alert_feedback`, `alert_suppressions`, `explanation`, `daily_alert_limit`, `max_length`, `/ready`, `/v1/admin/quality`.
- Scope check: the plan is broad but broken into independently testable phases; each phase can ship without enabling registration.
