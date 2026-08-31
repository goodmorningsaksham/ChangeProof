import zipfile
import json
import os

capsules = [
    "capsules/case-01.zip",
    "capsules/case-10.zip",
    "capsules/case-alt-01.zip",
    "capsules/case-calib-01.zip",
    "capsules/case-calib-02.zip",
    "capsules/case-var-01.zip",
    "capsules/case-var-02.zip",
    "capsules/case-var-03.zip",
    "capsules/case-var-04.zip",
    "capsules/case-var-05.zip",
]

for cap in capsules:
    print(f"=== {cap} ===")
    with zipfile.ZipFile(cap, "r") as z:
        for name in z.namelist():
            if "manifest.json" in name:
                data = json.loads(z.read(name).decode("utf-8"))
                if "base" in data and "patched" in data:
                    b = data["base"]
                    p = data["patched"]
                    print(f"  BASE: reqs={b.get('total_requests')}, dur={b.get('duration_s')}, tp={b.get('throughput_req_per_sec')}, rate={b.get('rate_per_min')}")
                    print(f"  PATCHED: reqs={p.get('total_requests')}, dur={p.get('duration_s')}, tp={p.get('throughput_req_per_sec')}, rate={p.get('rate_per_min')}")
                else:
                    print(f"  Top-level keys: {list(data.keys())}")
