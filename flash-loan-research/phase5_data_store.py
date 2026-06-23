#!/usr/bin/env python3
"""
Phase 5 Data Store

Persistent storage for execution metrics, pattern recognitions, and
long-running monitoring snapshots.

Storage model:
- SQLite primary store for fast local queries
- JSONL replica log for append-only event archival / lightweight distribution
- Snapshot export for dashboarding or node-to-node replication
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path('/root/.openclaw/workspace/flash-loan-research')
DB_PATH = BASE_DIR / 'phase5_metrics.db'
REPLICA_DIR = BASE_DIR / 'data' / 'replica'
REPLICA_LOG = REPLICA_DIR / 'metrics-events.jsonl'
SNAPSHOT_PATH = REPLICA_DIR / 'latest-metrics-snapshot.json'


@dataclass
class ExecutionMetricRecord:
    network: str
    opportunity_id: str
    detection_latency: float
    execution_latency: float
    profit: float
    success: bool
    pattern: Optional[str] = None
    playbook: Optional[str] = None
    risk_decision: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str = ''

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class PatternRecord:
    network: str
    opportunity_id: str
    pattern: str
    details: Dict[str, Any]
    timestamp: str = ''

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class MetricsStore:
    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        REPLICA_DIR.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS phase5_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                network TEXT NOT NULL,
                opportunity_id TEXT NOT NULL,
                detection_latency REAL NOT NULL,
                execution_latency REAL NOT NULL,
                profit REAL NOT NULL,
                success INTEGER NOT NULL,
                pattern TEXT,
                playbook TEXT,
                risk_decision TEXT,
                error_message TEXT
            )
            '''
        )
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS phase5_pattern_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                network TEXT NOT NULL,
                opportunity_id TEXT NOT NULL,
                pattern TEXT NOT NULL,
                details TEXT NOT NULL
            )
            '''
        )
        cur.execute(
            '''
            CREATE INDEX IF NOT EXISTS idx_phase5_logs_timestamp
            ON phase5_logs(timestamp)
            '''
        )
        cur.execute(
            '''
            CREATE INDEX IF NOT EXISTS idx_phase5_logs_network
            ON phase5_logs(network)
            '''
        )
        cur.execute(
            '''
            CREATE INDEX IF NOT EXISTS idx_phase5_pattern_logs_timestamp
            ON phase5_pattern_logs(timestamp)
            '''
        )
        conn.commit()
        conn.close()

    def record_execution(self, record: ExecutionMetricRecord) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            '''
            INSERT INTO phase5_logs(
                timestamp, network, opportunity_id, detection_latency,
                execution_latency, profit, success, pattern, playbook,
                risk_decision, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                record.timestamp,
                record.network,
                record.opportunity_id,
                record.detection_latency,
                record.execution_latency,
                record.profit,
                int(record.success),
                record.pattern,
                record.playbook,
                record.risk_decision,
                record.error_message,
            )
        )
        conn.commit()
        conn.close()
        self._append_replica_event('execution', asdict(record))

    def record_pattern(self, record: PatternRecord) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            '''
            INSERT INTO phase5_pattern_logs(timestamp, network, opportunity_id, pattern, details)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                record.timestamp,
                record.network,
                record.opportunity_id,
                record.pattern,
                json.dumps(record.details, sort_keys=True),
            )
        )
        conn.commit()
        conn.close()
        self._append_replica_event('pattern', {
            'timestamp': record.timestamp,
            'network': record.network,
            'opportunity_id': record.opportunity_id,
            'pattern': record.pattern,
            'details': record.details,
        })

    def recent_executions(self, limit: int = 25) -> List[Dict[str, Any]]:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            '''
            SELECT * FROM phase5_logs ORDER BY timestamp DESC LIMIT ?
            ''',
            (int(limit),)
        )
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows

    def recent_patterns(self, limit: int = 25) -> List[Dict[str, Any]]:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            '''
            SELECT * FROM phase5_pattern_logs ORDER BY timestamp DESC LIMIT ?
            ''',
            (int(limit),)
        )
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        for row in rows:
            try:
                row['details'] = json.loads(row['details'])
            except Exception:
                pass
        return rows

    def summary(self) -> Dict[str, Any]:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            '''
            SELECT
                COUNT(*) AS total_attempts,
                COALESCE(SUM(success), 0) AS successes,
                COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS failures,
                COALESCE(AVG(detection_latency), 0) AS avg_detection_latency,
                COALESCE(AVG(execution_latency), 0) AS avg_execution_latency,
                COALESCE(SUM(profit), 0) AS total_profit
            FROM phase5_logs
            '''
        )
        row = dict(cur.fetchone())
        conn.close()
        total_attempts = int(row['total_attempts']) if row['total_attempts'] is not None else 0
        successes = int(row['successes']) if row['successes'] is not None else 0
        row['success_rate'] = (successes / total_attempts) if total_attempts else 0.0
        row['total_attempts'] = total_attempts
        row['successes'] = successes
        row['failures'] = int(row['failures']) if row['failures'] is not None else 0
        return row

    def network_summary(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            '''
            SELECT
                network,
                COUNT(*) AS total_attempts,
                COALESCE(SUM(success), 0) AS successes,
                COALESCE(AVG(detection_latency), 0) AS avg_detection_latency,
                COALESCE(AVG(execution_latency), 0) AS avg_execution_latency,
                COALESCE(SUM(profit), 0) AS total_profit
            FROM phase5_logs
            GROUP BY network
            ORDER BY total_profit DESC, network ASC
            '''
        )
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        for row in rows:
            total_attempts = int(row['total_attempts']) if row['total_attempts'] is not None else 0
            successes = int(row['successes']) if row['successes'] is not None else 0
            row['success_rate'] = (successes / total_attempts) if total_attempts else 0.0
            row['total_attempts'] = total_attempts
            row['successes'] = successes
        return rows

    def export_snapshot(self) -> Dict[str, Any]:
        snapshot = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': self.summary(),
            'network_summary': self.network_summary(),
            'recent_executions': self.recent_executions(20),
            'recent_patterns': self.recent_patterns(20),
        }
        SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
        return snapshot

    def _append_replica_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {
            'event_type': event_type,
            'written_at': datetime.now(timezone.utc).isoformat(),
            'payload': payload,
        }
        with REPLICA_LOG.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(event, sort_keys=True) + '\n')


if __name__ == '__main__':
    store = MetricsStore()
    store.record_pattern(PatternRecord(
        network='arbitrum',
        opportunity_id='demo_pattern',
        pattern='vault_yield',
        details={'source': 'self-test'}
    ))
    store.record_execution(ExecutionMetricRecord(
        network='arbitrum',
        opportunity_id='demo_execution',
        detection_latency=42.0,
        execution_latency=1.1,
        profit=1500.0,
        success=True,
        pattern='vault_yield',
        playbook='vault_yield',
        risk_decision='allow'
    ))
    print(store.export_snapshot())
