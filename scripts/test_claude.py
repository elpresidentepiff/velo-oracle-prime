"""
Phase 6 — Claude API connection test
"""
import os, sys
from pathlib import Path

for line in Path(__file__).parent.parent.joinpath('.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())

api_key = os.environ.get('ANTHROPIC_API_KEY', '')
if not api_key:
    print('FAILED: ANTHROPIC_API_KEY not set in .env')
    sys.exit(1)

try:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=32,
        messages=[{'role': 'user', 'content': 'Reply with: VELO_CLAUDE_OK'}]
    )
    reply = msg.content[0].text.strip()
    print(f'Claude API: CONNECTED')
    print(f'Response: {reply}')
    print(f'Model: {msg.model}')
except ImportError:
    print('FAILED: anthropic package not installed. Run: pip install anthropic')
    sys.exit(1)
except Exception as e:
    print(f'FAILED: {e}')
    sys.exit(1)
