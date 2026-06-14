import sys

try:
    from evidently.report import Report
    print("SUCCESS: from evidently.report import Report")
except ImportError as e:
    print(f"FAILED: from evidently.report import Report ({e})")

try:
    from evidently.legacy.report import Report
    print("SUCCESS: from evidently.legacy.report import Report")
except ImportError as e:
    print(f"FAILED: from evidently.legacy.report import Report ({e})")

try:
    from evidently.metric_preset import DataDriftPreset
    print("SUCCESS: from evidently.metric_preset import DataDriftPreset")
except ImportError as e:
    print(f"FAILED: from evidently.metric_preset import DataDriftPreset ({e})")

try:
    from evidently.legacy.metric_preset import DataDriftPreset
    print("SUCCESS: from evidently.legacy.metric_preset import DataDriftPreset")
except ImportError as e:
    print(f"FAILED: from evidently.legacy.metric_preset import DataDriftPreset ({e})")
