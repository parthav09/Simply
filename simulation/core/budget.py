"""Persistent atomic campaign reservations, using integer microdollars."""
import json
import sqlite3
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path

PRICING = {'model': 'gemini-2.5-flash', 'as_of': '2026-10-27',
           'source': 'https://ai.google.dev/gemini-api/docs/pricing',
           'input_usd_per_million': 0.30, 'cached_usd_per_million': 0.03,
           'output_usd_per_million': 2.50}


class BudgetExhaustedError(RuntimeError):
    def __init__(self, message):
        super().__init__(message)
        self.telemetry={'request_submitted':False,'estimated_cost_micros':0,'usage':None,'budget_denied':True}


class RequestCancelledError(RuntimeError):
    """A cancelled queued proposal never reached the provider transport."""
    def __init__(self):
        super().__init__('Request not dispatched: session cancelled')
        self.telemetry={'request_submitted':False,'estimated_cost_micros':0,'usage':None,'cancelled':True}


def _snapshot(db):
    row=db.execute('SELECT limit_micros FROM campaign WHERE id=1').fetchone()
    if row is None:raise ValueError('Campaign ledger has no limit record')
    limit=row[0]
    known,reserved,count=db.execute('SELECT coalesce(sum(actual),0),coalesce(sum(CASE WHEN actual IS NULL THEN reserved ELSE 0 END),0),count(*) FROM requests').fetchone()
    return {'limit_usd':limit/1e6,'known_estimated_usd':known/1e6,
            'unresolved_reserved_usd':reserved/1e6,'requests':count,
            'remaining_usd':max(0,(limit-known-reserved)/1e6)}


def read_ledger_snapshot(path):
    """Read existing evidence without creating, migrating or resetting a ledger."""
    path=Path(path)
    if not path.is_file():return None
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=30) as db:
            db.execute('BEGIN')
            return _snapshot(db)
    except sqlite3.Error as error:
        raise ValueError('Campaign ledger is unreadable; its totals are unknown') from error


def usage_cost_micros(usage, pricing=None):
    pricing = pricing or PRICING
    if not usage or any(usage.get(k) is None for k in ('promptTokenCount', 'candidatesTokenCount')):
        return None
    prompt = usage['promptTokenCount']
    cached = usage.get('cachedContentTokenCount', 0)
    output = usage['candidatesTokenCount'] + usage.get('thoughtsTokenCount', 0)
    if any(type(v) is not int or v < 0 for v in (prompt, cached, output)) or cached > prompt:
        raise ValueError('Invalid provider usage')
    writes=usage.get('cacheWriteTokenCount',0)
    if type(writes) is not int or writes<0 or writes>prompt-cached:raise ValueError('Invalid cache write usage')
    short=usage.get('cacheWrite30mTokenCount',writes)
    long=usage.get('cacheWrite12hTokenCount',0)
    if type(short) is not int or type(long) is not int or min(short,long)<0 or short+long!=writes:raise ValueError('Invalid cache write lifetimes')
    return round((prompt-cached-writes)*pricing['input_usd_per_million'] + cached*pricing['cached_usd_per_million'] + short*pricing.get('cache_write_usd_per_million',pricing['input_usd_per_million']) + long*pricing.get('cache_write_12h_usd_per_million',pricing['input_usd_per_million']) + output*pricing['output_usd_per_million'])


class CampaignLedger:
    def __init__(self, path, limit_usd=10.0, *, enforce_limit=True):
        if type(enforce_limit) is not bool:
            raise ValueError('enforce_limit must be a boolean')
        if not 0 < limit_usd <= 10:
            raise ValueError('Campaign limit must be greater than zero and at most $10')
        self.path = Path(path)
        self.enforce_limit = enforce_limit
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS campaign (id INTEGER PRIMARY KEY CHECK(id=1), limit_micros INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO campaign VALUES (1, ?)', (round(limit_usd * 1_000_000),))
            db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, run_id TEXT, reserved INTEGER, actual INTEGER, usage TEXT, created TEXT)')
            if 'bucket' not in [r[1] for r in db.execute('PRAGMA table_info(requests)')]:
                db.execute("ALTER TABLE requests ADD COLUMN bucket TEXT NOT NULL DEFAULT 'manual'")
            db.execute('CREATE TABLE IF NOT EXISTS stages (bucket TEXT PRIMARY KEY, limit_micros INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS admission (id INTEGER PRIMARY KEY CHECK(id=1), dispatched_at REAL NOT NULL)')
            # A later process may tighten a limit, never raise it implicitly.
            db.execute('UPDATE campaign SET limit_micros = min(limit_micros, ?) WHERE id=1', (round(limit_usd * 1_000_000),))

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def acquire_slot(self, requests_per_minute, cancelled):
        """Pace new admissions across processes; never retry a failed request."""
        if cancelled.is_set():
            raise RequestCancelledError()
        if requests_per_minute == 0:
            return
        interval = 60 / requests_per_minute
        while True:
            if cancelled.is_set():
                raise RequestCancelledError()
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT dispatched_at FROM admission WHERE id=1').fetchone()
                now=time.time()
                wait=max(0,(row[0] if row else now-interval)+interval-now)
                if wait <= 0:
                    db.execute('INSERT OR REPLACE INTO admission VALUES (1,?)',(now,))
                    return
            cancelled.wait(min(wait,.2))

    def reserve(self, run_id, prompt, max_output_tokens=256, extra_bytes=0, bucket="manual", stage_limit_usd=None, pricing=None):
        pricing = pricing or PRICING
        # Conservatively use one input token per serialized UTF-8 byte, plus
        # wrapper/schema overhead. Unknown usage retains this full reservation.
        tokens = len(prompt.encode('utf-8')) + extra_bytes + 4096
        amount = round(tokens * max(pricing['input_usd_per_million'],pricing.get('cache_write_usd_per_million',0),pricing.get('cache_write_12h_usd_per_million',0)) + max_output_tokens*pricing['output_usd_per_million']) + 100
        request_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            limit = db.execute('SELECT limit_micros FROM campaign WHERE id=1').fetchone()[0]
            spent = db.execute('SELECT coalesce(sum(coalesce(actual,reserved)),0) FROM requests').fetchone()[0]
            if self.enforce_limit and spent + amount > limit:
                raise BudgetExhaustedError('Campaign budget exhausted before request dispatch')
            if self.enforce_limit and stage_limit_usd is not None:
                db.execute('INSERT OR IGNORE INTO stages VALUES (?,?)',(bucket,round(stage_limit_usd*1e6)))
                stage_limit=db.execute('SELECT limit_micros FROM stages WHERE bucket=?',(bucket,)).fetchone()[0]
                stage_spent=db.execute('SELECT coalesce(sum(coalesce(actual,reserved)),0) FROM requests WHERE bucket=?',(bucket,)).fetchone()[0]
                if stage_spent+amount>stage_limit:
                    raise BudgetExhaustedError(f'Campaign budget exhausted for stage {bucket}')
            db.execute('INSERT INTO requests (id,run_id,reserved,actual,usage,created,bucket) VALUES (?,?,?,?,?,?,?)',
                       (request_id, run_id, amount, None, None, datetime.now(timezone.utc).isoformat(),bucket))
        return request_id, amount

    def settle(self, request_id, usage, pricing=None):
        actual = usage_cost_micros(usage,pricing)
        with self.connect() as db:
            db.execute('UPDATE requests SET actual=?,usage=? WHERE id=?',
                       (actual, json.dumps(usage) if usage else None, request_id))
        return actual

    def snapshot(self):
        with self.connect() as db:
            db.execute('BEGIN')
            return _snapshot(db)
