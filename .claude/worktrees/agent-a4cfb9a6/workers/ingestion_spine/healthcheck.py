#!/usr/bin/env python3
"""Health check script for Railway deployment."""
import os
import sys
import urllib.request

def main():
    port = os.environ.get('PORT', '8000')
    url = f'http://localhost:{port}/health'
    
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status == 200:
                sys.exit(0)
            else:
                sys.exit(1)
    except Exception as e:
        print(f"Health check failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
