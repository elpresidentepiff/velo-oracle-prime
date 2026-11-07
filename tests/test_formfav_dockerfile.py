from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_formfav_image_contains_every_live_worker_module():
    dockerfile = (ROOT / "Dockerfile.formfav").read_text()
    required = {
        "src/velo/formfav_client.py",
        "src/velo/formfav_feature_contract.py",
        "src/velo/formfav_evidence_store.py",
        "scripts/ops/formfav_live_worker.py",
    }
    assert all(f"COPY {path} {path}" in dockerfile for path in required)
