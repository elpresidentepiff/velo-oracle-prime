#!/usr/bin/env python3
"""
VÉLØ Playbook G Live Adapter

Authorized 2026-07-26 (operator sign-off) to update data/sentient_state.json
directly, after: (1) the doctrines_fired hardcoded-[] bug in
playbook_g_shadow_adapter.py was found and fixed, (2) the shadow state was
backfilled and cross-checked for consistency, (3) the live state was caught
up from its 2026-04-25 freeze point using the same real historical data
(scripts/ops/catchup_playbook_g_live_state.py).

Reuses PlaybookGShadowAdapter's exact event-preparation and regression-guard
logic (including the doctrines_fired-dropped check) via inheritance, only
overriding the shadow-file-only safety gate -- and only when explicitly
constructed with authorized=True. Never called with authorized=True except
from scripts/ops/nightly_eod_learning_runner.py, and only after that night's
shadow pass has already PASSED (proving idempotency + no doctrine-drop
regression on the identical event file).
"""
import json
from pathlib import Path

from scripts.playbook_g_shadow_adapter import PlaybookGShadowAdapter
from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine


class PlaybookGLiveAdapter(PlaybookGShadowAdapter):
    def __init__(self, events_path: str, state_path: str, audit_path: str, authorized: bool = False):
        if not authorized:
            raise ValueError(
                "PlaybookGLiveAdapter requires authorized=True. This is not a default -- "
                "it exists specifically to write data/sentient_state.json, and must only "
                "be constructed after an explicit operator decision."
            )

        # Deliberately skip PlaybookGShadowAdapter.__init__ (it hard-blocks
        # non-shadow state paths); duplicate its setup here instead.
        self.events_path = Path(events_path)
        self.state_path = Path(state_path)
        self.audit_path = Path(audit_path)

        self.processed_keys = set()
        if self.audit_path.exists():
            try:
                prev_audit = json.loads(self.audit_path.read_text())
                self.processed_keys = set(prev_audit.get("processed_keys", []))
            except Exception:
                pass

        self.engine = SentientLoopbackEngine(state_file=str(self.state_path), disable_cloud_backup=True)

        self.audit = {
            "events_read": 0,
            "events_learning_allowed_true": 0,
            "events_skipped_learning_not_allowed": 0,
            "events_skipped_duplicate": 0,
            "engine_updates_attempted": 0,
            "engine_updates_applied": 0,
            "live_state_touched": False,
            "shadow_state_touched": False,
            "supabase_backup_attempted": False,
            "hfs_read_attempted": False,
            "doctrines_fired_dropped": 0,
            "processed_keys": list(self.processed_keys),
            "verdict": "UNKNOWN",
        }

    def run(self):
        super().run()
        # Parent's run() hardcodes live_state_touched=False and only ever
        # sets shadow_state_touched=True (it assumes it's always the shadow
        # adapter). Correct the audit labels for this, the live, adapter.
        if self.audit.get("shadow_state_touched"):
            self.audit["live_state_touched"] = True
            self.audit["shadow_state_touched"] = False
            self.audit_path.write_text(json.dumps(self.audit, indent=2))
