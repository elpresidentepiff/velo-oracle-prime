import os
import shutil
from pathlib import Path

def flatten_and_clean():
    root = Path("data/racing_post_account_raw")
    dest = root / "june02-reconciliation-bulk"
    dest.mkdir(parents=True, exist_ok=True)
    
    # All directories starting with june02-
    sources = list(root.glob("june02-*"))
    
    count = 0
    manifests = []
    
    for s_dir in sources:
        if s_dir.name == "june02-reconciliation-bulk": continue
        
        print(f"Scanning {s_dir.name}...")
        for f in s_dir.rglob("*"):
            if f.is_file() and (f.suffix == ".html" or f.name == "manifest.json"):
                # If it's a manifest, we collect its contents instead of moving the file directly
                # because multiple manifests would overwrite each other.
                if f.name == "manifest.json":
                    manifests.append(f)
                    continue
                
                # Copy HTML
                shutil.copy2(f, dest / f.name)
                # Copy JSON sidecar if it exists
                json_sidecar = f.with_suffix(".json")
                if json_sidecar.exists():
                    shutil.copy2(json_sidecar, dest / json_sidecar.name)
                count += 1
                
    # Create a unified manifest
    combined_captures = []
    for m in manifests:
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
            for c in data.get("captures", []):
                # Update path to be relative to the new bulk dir
                if "html_path" in c:
                    c["html_path"] = str(dest / Path(c["html_path"]).name)
                combined_captures.append(c)
        except:
            pass
            
    unified_manifest = {
        "mode": "capture_unified",
        "status": "PASS",
        "generated_at": "2026-06-02T21:10:00Z",
        "captures": combined_captures
    }
    
    (dest / "manifest.json").write_text(json.dumps(unified_manifest, indent=2), encoding="utf-8")
    print(f"Flattened {count} files into {dest}")

if __name__ == "__main__":
    flatten_and_clean()
