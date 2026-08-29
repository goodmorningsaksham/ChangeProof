from changeproof.replay import replay_capsule

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
    res = replay_capsule(cap, mode="evidence")
    ver = res.get("verification", {})
    pre = ver.get("pre_summary", {})
    post = ver.get("post_summary", {})
    status = ver.get("status")
    print(f"{cap:30s} | VERDICT: [{status}]")
    print(f"   BASE:    retries/req={pre.get('retries_per_request')} | reqs={pre.get('total_requests')} | tp={pre.get('throughput_req_per_sec')} req/s | rate={pre.get('rate_per_min')} /min")
    print(f"   PATCHED: retries/req={post.get('retries_per_request')} | reqs={post.get('total_requests')} | tp={post.get('throughput_req_per_sec')} req/s | rate={post.get('rate_per_min')} /min")
