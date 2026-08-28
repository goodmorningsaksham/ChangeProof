"""Proof certificate rendering module."""
from jinja2 import Template
from typing import Dict, Any

DEFAULT_MD_TEMPLATE = """# CHANGE PROOF CERTIFICATE
Generated: {{ timestamp }} | Experiment: {{ experiment_id }} | Commit: {{ git_commit }}

## Evaluation Summary
- **Risk Level**: {{ risk_level }} (Score: {{ risk_score }}/100)
- **Failure Class**: Retry Amplification / Retry Storm
- **Hypothesis**: {{ hypothesis_title }} (Confidence: {{ hypothesis_confidence }})
- **Deterministic Verification**: **{{ verification_status }}**

## Evidence Comparison
| Metric | Phase | Observed Value | Condition | Condition Met |
|---|---|---|---|---|
{% for row in diff_table %}
| {{ row.metric }} | {{ row.phase }} | {{ row.observed_value }} | `{{ row.condition }}` | {{ "YES" if row.condition_met else "NO" }} |
{% endfor %}

## Reproducibility & Artifacts
- **Reproduction Capsule**: `{{ capsule_path }}`
- **Replay Command**: `python changeproof/replay.py {{ capsule_path }}`

## Human Engineering Decision
[ ] APPROVED FOR DEPLOYMENT   [ ] REJECTED   [ ] ESCALATE FOR REVIEW
Reviewer Signature: _______________________ Date: _______________
"""

class CertificateGenerator:
    def __init__(self, template_str: str = DEFAULT_MD_TEMPLATE):
        self.template = Template(template_str)

    def render(self, context: Dict[str, Any]) -> str:
        return self.template.render(context)

    def generate_and_save(self, context: Dict[str, Any], output_path: str) -> str:
        content = self.render(context)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return output_path
