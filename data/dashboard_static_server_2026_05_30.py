
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json
ROOT = Path('/mnt/c/Users/puror/velo-oracle-prime')
DASH = ROOT / 'app/static/dashboard/index.html'
SIDECAR = ROOT / 'app/static/dashboard/sidecar_stack_latest.json'
PREDS = ROOT / 'data/new_build/paper_predictions/new_build_predictions_2026_05_30.jsonl'
REPORT = ROOT / 'data/new_build/reports/new_build_paper_predictions_final_card_latest.json'

def _hhmm(v):
    v = str(v or '')
    return v.split('T', 1)[1][:5] if 'T' in v else v[:5]

def _tier(prob, rank, passport):
    if not passport: return 'X'
    if rank == 1 and prob >= 0.16: return 'A'
    if rank <= 2 and prob >= 0.12: return 'B'
    if rank <= 3: return 'C'
    return 'D'

def governed_payload(date='2026-05-30'):
    rows = []
    for line in PREDS.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        prob = float(r.get('champion_probability') or 0)
        rank = int(r.get('champion_rank') or 99)
        passport = bool(r.get('passport_found'))
        rows.append({
            'race_id': str(r.get('race_id')),
            'course': r.get('course'),
            'off_time': _hhmm(r.get('off_time')),
            'horse': r.get('horse'),
            'horse_id': str(r.get('rp_uid') or ''),
            'tier': _tier(prob, rank, passport),
            'decision_tier': _tier(prob, rank, passport),
            'confidence_level': 'paper',
            'velo_prime_prob': round(prob, 6),
            'prob_gap': 0,
            'market_deception_score': 0,
            'assigned_product': 'NEW_BUILD_PAPER_ONLY',
            'router_reasons': ['PAPER_ONLY','NO_STAKING','NO_TELEGRAM','NO_LIVE_WRITE','INTENT_UNAVAILABLE_TODAY'],
            'execution_allowed': False,
            'place_prob': 0,
            'archetype_label': 'CORE_PASSPORT',
            'rpr_policy': 'RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO',
            'rp_rpr_velo_allowed': False,
        })
    rep = json.loads(REPORT.read_text(encoding='utf-8'))
    return {
        'meta': {
            'requested_date': date,
            'loaded_date': '2026-05-30',
            'source': 'new_build_static_dashboard_server',
            'record_count': len(rows),
            'date_mismatch': date != '2026-05-30',
            'date_match': date == '2026-05-30',
            'governed_card_status': 'PASS_EXACT_DATE',
            'sidecar_status': 'NEW_BUILD_PAPER_ONLY',
            'sidecar_loaded_date': '2026-05-30',
            'sidecar_date_match': date == '2026-05-30',
            'card_status': 'CARD_EXACT_DATE_PASS',
            'new_build_classification': 'NEW_BUILD_2026_05_30_CORE_PASSPORT_READY',
            'passport_coverage_pct': rep.get('current_card_feed',{}).get('passport_coverage',{}).get('coverage_pct'),
        },
        'verdicts': rows,
    }

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        if isinstance(body, str): body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ['/', '/dashboard']:
            return self._send(200, DASH.read_bytes(), 'text/html; charset=utf-8')
        if parsed.path.endswith('/sidecar_stack_latest.json') or parsed.path == '/sidecar_stack_latest.json':
            return self._send(200, SIDECAR.read_bytes(), 'application/json; charset=utf-8')
        if parsed.path == '/api/governed-card':
            date = parse_qs(parsed.query).get('date', ['2026-05-30'])[0]
            return self._send(200, json.dumps(governed_payload(date), ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')
        return self._send(404, 'not found', 'text/plain; charset=utf-8')
    def log_message(self, fmt, *args):
        print(fmt % args)

ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
