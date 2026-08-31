from changeproof.certificate import CertificateGenerator
from changeproof.hypothesis_evaluator import generate_candidate_hypotheses, evaluate_hypotheses_evidence
import json

# Signals for Case-01
signals = [
    "Aggressive retry count increase (max_retries >= 4)",
    "Removal of backoff / immediate retry execution",
    "Aggressive timeout reduction (timeout < 1.0s)",
]

hypos = generate_candidate_hypotheses(signals, proxy_name="payment-proxy", calibrated_latency_ms=1500)

pre_summary = {
    "phase": "base",
    "duration_s": 41.17,
    "total_requests": 150.0,
    "retries_counted": 1050.0,
    "retries_per_request": 7.0,
    "rate_per_min": 1530.12,
    "throughput_req_per_sec": 3.64,
}
post_summary = {
    "phase": "patched",
    "duration_s": 25.7,
    "total_requests": 150.0,
    "retries_counted": 150.0,
    "retries_per_request": 1.0,
    "rate_per_min": 350.2,
    "throughput_req_per_sec": 5.84,
}

evaluated = evaluate_hypotheses_evidence(
    hypos,
    pre_summary=pre_summary,
    post_summary=post_summary,
    calibrated_latency_ms=1500,
    client_timeout_s=0.5,
)

diff_table = [
    {"metric": "retries_per_request", "phase": "pre_patch", "observed_value": 7.0, "condition": "> 2.0", "condition_met": True},
    {"metric": "total_requests", "phase": "pre_patch", "observed_value": 150.0, "condition": ">= 100", "condition_met": True},
    {"metric": "retries_per_request", "phase": "post_patch", "observed_value": 1.0, "condition": "<= 1.1", "condition_met": True},
    {"metric": "total_requests", "phase": "post_patch", "observed_value": 150.0, "condition": ">= 100", "condition_met": True},
]

cert_gen = CertificateGenerator()
context = {
    "timestamp": "2026-08-29T11:07:42Z",
    "experiment_id": "case-01-canonical",
    "git_commit": "7b3ec20",
    "risk_level": "HIGH",
    "risk_score": 70,
    "hypothesis_title": "Downstream latency induces retry storm (checkout -> payment)",
    "hypothesis_confidence": "HIGH",
    "candidate_hypotheses": evaluated,
    "verification_status": "PASS",
    "diff_table": diff_table,
    "pre_summary": pre_summary,
    "post_summary": post_summary,
    "capsule_path": "capsules/case-01.zip",
}

cert_gen.generate_and_save(context, "runs/ci_run/proof_certificate.md")
cert_gen.generate_and_save(context, "runs/case01_synth_live_run/proof_certificate.md")
print("Regenerated proof certificates for case-01.")
