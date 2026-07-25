import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

FORBIDDEN_COUNCIL_EVIDENCE_TERMS = ("racing api",)

# Phrases that, near a "racing api" mention, indicate the text is declaring
# the ban rather than citing Racing API as a live evidence/data source.
# Confirmed 2026-07-11: a bare substring match on "racing api" false-positived
# on docs/current/ONE_TRUTH.md itself ("Racing API is PERMANENTLY DECOMMISSIONED
# for live use"), which would make the current canonical truth file permanently
# fail this gate. The hard law only forbids Racing API as a live evidence
# SOURCE (see CLAUDE.md/THE_ONE_TRUTH.md), not documentation stating the ban.
_BANNING_LANGUAGE_WINDOW = 120
_BANNING_LANGUAGE_TERMS = (
    "decommission", "permanently", "no longer", "not live", "is not connected",
    "must not", "banned", "ban ", "must never", "never call", "never depend",
    "blocker", "archived legacy", "deleted", "do not use", "does not exist",
    "is stale", "client files deleted",
)


def _forbidden_term_is_live_usage(content_lower: str, term: str) -> bool:
    """True if `term` appears in `content_lower` outside the context window
    of banning/deprecation language -- i.e. looks like a live evidence
    source citation, not a statement that the source is forbidden."""
    start = 0
    while True:
        idx = content_lower.find(term, start)
        if idx == -1:
            return False
        window = content_lower[
            max(0, idx - _BANNING_LANGUAGE_WINDOW): idx + len(term) + _BANNING_LANGUAGE_WINDOW
        ]
        if not any(b in window for b in _BANNING_LANGUAGE_TERMS):
            return True
        start = idx + len(term)


class EvidencePacket:
    def __init__(self, date_str: str):
        self.date_str = date_str
        # Support both 2026-05-01 and 2026_05_01
        self.alt_date_str = date_str.replace("-", "_")
        
        self.data = {
            "metadata": {
                "date": date_str,
                "alt_date": self.alt_date_str,
                "generated_at": datetime.now().isoformat(),
                "status": "INITIALIZING",
                "council_status": "PENDING"
            },
            "evidence_sources": {},
            "verdicts": []
        }

    def load_all_evidence(self, repo_root: Path):
        """Loads evidence from known data paths with dual-date support."""
        
        # VP30
        self._find_evidence(
            "vp30_operator_card",
            [
                f"data/vp30_operator_card_{self.date_str}.md",
                f"data/vp30_operator_card_{self.alt_date_str}.md",
                # Also check place_signal variant if that's what was built
                f"data/place_signal_operator_card_{self.date_str}.md",
                f"data/place_signal_operator_card_{self.alt_date_str}.md"
            ],
            repo_root,
            required=True
        )

        # Cashrun
        self._find_evidence(
            "cashrun_report",
            [
                f"data/cashrun_report_{self.date_str}.md",
                f"data/cashrun_report_{self.alt_date_str}.md"
            ],
            repo_root
        )

        # Live Sidecar Audit
        self._find_evidence(
            "live_sidecar_audit",
            [
                "data/live_sidecar_ablation_audit_latest.md",
                "data/live_sidecar_ablation_audit_latest.json"
            ],
            repo_root
        )

        # Router Audit
        self._find_evidence(
            "router_shadow_audit",
            [
                "data/router_shadow_audit_latest.md",
                "data/router_shadow_audit_latest.csv"
            ],
            repo_root
        )

        # Execution Bridge Ledger
        self._find_evidence(
            "execution_bridge_ledger",
            [
                "data/velo_execution_bridge_paper_ledger.csv"
            ],
            repo_root
        )

        # One Truth — docs/current/ONE_TRUTH.md is the actual canonical truth
        # per CLAUDE.md's own header ("SINGLE SOURCE OF TRUTH"). The old
        # wiring map doc predates the Racing API decommission and still
        # documents that dead architecture verbatim, which legitimately
        # trips the forbidden-evidence check below. Try the canonical file
        # first; keep the old doc only as a fallback if it's ever missing.
        self._find_evidence(
            "one_truth_file",
            [
                "docs/current/ONE_TRUTH.md",
                "docs/engineering/VELO_PROCESS_WIRING_MAP_V1.md"
            ],
            repo_root,
            required=True
        )

        # Final Council Status Check
        required_missing = [
            name for name, info in self.data["evidence_sources"].items()
            if info["required_for_release"] and info["status"] == "MISSING"
        ]
        forbidden_sources = [
            name for name, info in self.data["evidence_sources"].items()
            if any(
                _forbidden_term_is_live_usage(str(info.get("content") or "").lower(), term)
                for term in FORBIDDEN_COUNCIL_EVIDENCE_TERMS
            )
        ]
        
        if required_missing or forbidden_sources:
            self.data["metadata"]["council_status"] = "EVIDENCE_INCOMPLETE"
            self.data["metadata"]["status"] = "INCOMPLETE"
            self.data["metadata"]["forbidden_evidence_sources"] = forbidden_sources
        else:
            self.data["metadata"]["council_status"] = "READY"
            self.data["metadata"]["status"] = "LOADED"
            
        return self.data

    def _find_evidence(self, name: str, paths: List[str], root: Path, required: bool = False):
        found_path = None
        content = None
        status = "MISSING"
        
        for p_str in paths:
            p = root / p_str
            if p.exists():
                found_path = str(p_str)
                status = "FOUND"
                # For large files or CSVs, we might just note existence
                if p.suffix in ['.md', '.txt', '.json']:
                    try:
                        content = p.read_text()
                    except:
                        content = "UNREADABLE"
                else:
                    content = f"BINARY_OR_CSV_PRESENT: {p.suffix}"
                break
        
        self.data["evidence_sources"][name] = {
            "source_name": name,
            "status": status,
            "path": found_path,
            "date_matched": self.date_str if status == "FOUND" else None,
            "required_for_release": required,
            "label": "SHADOW", # Default label
            "content": content
        }

    def save_packet(self, root: Path):
        out_path = root / f"data/council_packets/council_packet_{self.date_str}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w') as f:
            # We strip content for the summary metadata if needed, 
            # but usually the packet JSON includes it for the LLM.
            json.dump(self.data, f, indent=2)
        return out_path
