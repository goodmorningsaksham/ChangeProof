"""Topology-driven experiment specification synthesizer for ChangeProof."""
import os
import re
import json
import yaml
from typing import Dict, Any, List, Optional, Tuple


def _clean_service_name(name: str) -> str:
    """Normalize service name (e.g. 'checkout-service' -> 'checkout')."""
    return name.replace("-service", "").replace("_service", "")


class ExperimentSynthesizer:
    """Synthesizes deterministic experiment.yaml specs from diff and topology."""

    def __init__(
        self,
        compose_path: str = "docker-compose.yml",
        toxiproxy_config_path: str = "toxiproxy_init.json",
    ):
        self.compose_path = compose_path
        self.toxiproxy_config_path = toxiproxy_config_path

    def _load_compose(self) -> Dict[str, Any]:
        if not os.path.exists(self.compose_path):
            raise FileNotFoundError(f"Docker compose file not found: {self.compose_path}")
        with open(self.compose_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_toxiproxy_config(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.toxiproxy_config_path):
            try:
                with open(self.toxiproxy_config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        return []

    def resolve_changed_service(self, pr_diff: str, compose_data: Dict[str, Any]) -> str:
        """Step 1: Match changed file in diff to a service in compose build context."""
        changed_files = []
        for line in pr_diff.splitlines():
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                filepath = line[6:].strip()
                if filepath not in changed_files:
                    changed_files.append(filepath)
            elif line.startswith("diff --git a/"):
                parts = line.split()
                if len(parts) >= 3:
                    f = parts[2][2:].strip()
                    if f not in changed_files:
                        changed_files.append(f)

        services = compose_data.get("services", {})
        
        # 1a. Direct build context match
        for fpath in changed_files:
            norm_f = os.path.normpath(fpath).replace("\\", "/")
            for s_name, s_cfg in services.items():
                build_cfg = s_cfg.get("build", {})
                if isinstance(build_cfg, str):
                    ctx = os.path.normpath(build_cfg).replace("\\", "/")
                elif isinstance(build_cfg, dict):
                    ctx = os.path.normpath(build_cfg.get("context", "")).replace("\\", "/")
                else:
                    ctx = ""
                
                if ctx and ctx != ".":
                    clean_ctx = ctx.lstrip("./").rstrip("/")
                    if norm_f.startswith(clean_ctx) or f"/{clean_ctx}/" in f"/{norm_f}":
                        return s_name

        # 1b. Fallback: service name / directory substring match
        for fpath in changed_files:
            norm_f = os.path.normpath(fpath).replace("\\", "/")
            for s_name in services.keys():
                s_short = _clean_service_name(s_name)
                if f"/{s_short}/" in f"/{norm_f}" or norm_f.startswith(s_short):
                    return s_name

        if not services:
            raise ValueError(f"No services found in {self.compose_path}")

        # If exactly one app service (excluding toxiproxy/prometheus), choose it
        app_services = [s for s in services.keys() if s not in ("toxiproxy", "prometheus")]
        if len(app_services) == 1:
            return app_services[0]

        raise ValueError(
            f"Could not resolve changed file {changed_files} to any service in {self.compose_path}"
        )

    def resolve_changed_file(self, pr_diff: str, changed_service: str) -> str:
        """Resolves the exact file path modified in the changed service."""
        for line in pr_diff.splitlines():
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                path = line.split("/", 1)[-1].strip()
                if os.path.exists(path):
                    return path
                clean_path = re.sub(r"^[ab]/", "", path)
                if os.path.exists(clean_path):
                    return clean_path

        s_clean = _clean_service_name(changed_service)
        candidates = [
            f"app/{s_clean}/main.py",
            f"app/{changed_service}/main.py",
            f"{s_clean}/main.py",
            f"src/{s_clean}/main.py",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return f"app/{s_clean}/main.py"
    def resolve_downstream_dependency(
        self,
        service_name: str,
        compose_data: Dict[str, Any],
        pr_diff: str,
    ) -> Tuple[str, Optional[int]]:
        """Step 2: Identify downstream target service from environment and diff."""
        services = compose_data.get("services", {})
        s_cfg = services.get(service_name, {})
        env = s_cfg.get("environment", [])

        # Parse env list or dict into dict
        env_dict: Dict[str, str] = {}
        if isinstance(env, list):
            for item in env:
                if "=" in item:
                    k, v = item.split("=", 1)
                    env_dict[k.strip()] = v.strip()
        elif isinstance(env, dict):
            env_dict = {str(k): str(v) for k, v in env.items()}

        url_candidates: List[Tuple[str, str]] = []
        for k, v in env_dict.items():
            if k.endswith("_URL") or "_SERVICE_URL" in k or k == "PAYMENT_URL":
                url_candidates.append((k, v))

        if not url_candidates:
            # Check depends_on excluding toxiproxy/prometheus
            deps = s_cfg.get("depends_on", [])
            if isinstance(deps, dict):
                deps = list(deps.keys())
            candidates = [d for d in deps if d not in ("toxiproxy", "prometheus")]
            if len(candidates) == 1:
                return candidates[0], None
            elif not candidates and "toxiproxy" in deps:
                # Toxiproxy is dependency; resolve target through toxiproxy depends_on
                toxi_cfg = services.get("toxiproxy", {})
                toxi_deps = toxi_cfg.get("depends_on", [])
                if isinstance(toxi_deps, dict):
                    toxi_deps = list(toxi_deps.keys())
                downstream = [d for d in toxi_deps if d != "prometheus"]
                if len(downstream) == 1:
                    return downstream[0], None

        if len(url_candidates) > 1:
            # Disambiguate via mentions in pr_diff
            diff_matched = [c for c in url_candidates if c[0] in pr_diff or _clean_service_name(c[0]) in pr_diff]
            if len(diff_matched) == 1:
                url_candidates = diff_matched
            else:
                raise ValueError(
                    f"Ambiguous downstream dependencies for {service_name}: {[c[0] for c in url_candidates]}. "
                    "Cannot silently choose without explicit diff reference."
                )

        if url_candidates:
            target_var, target_url = url_candidates[0]
            # Parse port if present
            port = None
            m_port = re.search(r":(\d+)", target_url)
            if m_port:
                port = int(m_port.group(1))

            # If pointing to toxiproxy, resolve actual target service via toxiproxy config or depends_on
            if "toxiproxy" in target_url:
                toxi_config = self._load_toxiproxy_config()
                if port and toxi_config:
                    for entry in toxi_config:
                        listen = entry.get("listen", "")
                        if f":{port}" in listen:
                            upstream = entry.get("upstream", "")
                            up_host = upstream.split(":")[0]
                            if up_host in services:
                                return up_host, port

                # Check toxiproxy depends_on in compose
                toxi_deps = services.get("toxiproxy", {}).get("depends_on", [])
                if isinstance(toxi_deps, dict):
                    toxi_deps = list(toxi_deps.keys())
                candidates = [d for d in toxi_deps if d not in ("prometheus", "toxiproxy")]
                if len(candidates) == 1:
                    return candidates[0], port

            # Match URL hostname to known app services (excluding toxiproxy/prometheus)
            for s in services.keys():
                if s not in ("toxiproxy", "prometheus") and s in target_url:
                    return s, port

            # Fallback: derive name from env key (e.g. PAYMENT_SERVICE_URL -> payment-service)
            candidate_base = target_var.replace("_SERVICE_URL", "").replace("_URL", "").lower()
            for s in services.keys():
                if s not in ("toxiproxy", "prometheus") and candidate_base in s:
                    return s, port

        raise ValueError(f"Could not resolve downstream dependency for service {service_name}")

    def resolve_fault_proxy(
        self,
        service_name: str,
        target_service: str,
        target_port: Optional[int],
        compose_data: Dict[str, Any],
    ) -> Tuple[str, str]:
        """Step 3: Resolve Toxiproxy proxy name and admin URL."""
        toxi_cfg = compose_data.get("services", {}).get("toxiproxy", {})
        admin_port = 8474
        for p in toxi_cfg.get("ports", []):
            p_str = str(p)
            if "8474" in p_str:
                admin_port = 8474
                break

        admin_url = f"http://localhost:{admin_port}"

        # Try to find proxy name in toxiproxy_init.json
        toxi_config = self._load_toxiproxy_config()
        if toxi_config:
            for entry in toxi_config:
                upstream = entry.get("upstream", "")
                listen = entry.get("listen", "")
                if target_service in upstream or (target_port and f":{target_port}" in listen):
                    return entry.get("name", "payment-proxy"), admin_url

        # Canonical fallback proxy naming: {target_clean}-proxy
        target_clean = _clean_service_name(target_service)
        return f"{target_clean}-proxy", admin_url

    def resolve_fault_magnitude(self, pr_diff: str, compose_data: Dict[str, Any], service_name: str) -> Tuple[int, int]:
        """Step 4: Calibrate fault magnitude based on client timeout.

        Formula:
          injected_latency_ms = max(2 * timeout_ms, 1500)
          jitter_ms = max(int(0.05 * injected_latency_ms), 50)

        Empirical basis:
          CASE-01 and CASE-10 empirical calibrations established that for retry
          amplification to reproduce reliably under downstream latency, the injected
          fault latency must exceed the client per-attempt timeout by a sufficient
          margin (>= 2x) to consistently trigger timeout exceptions and prevent
          premature success, while staying within gateway deadline bounds.
        """
        timeout_s: Optional[float] = None

        # Look in diff for timeout overrides
        m_diff = re.search(r"^\+\s*RETRY_TIMEOUT_SECONDS\s*=\s*(?:float\(os\.getenv\([^,]+,\s*[\"']?([0-9.]+)[\"']?\)\)|([0-9.]+))", pr_diff, re.MULTILINE)
        if m_diff:
            val = m_diff.group(1) or m_diff.group(2)
            try:
                timeout_s = float(val)
            except ValueError:
                pass

        if timeout_s is None:
            # Check compose env
            s_env = compose_data.get("services", {}).get(service_name, {}).get("environment", [])
            env_str = str(s_env)
            m_env = re.search(r"RETRY_TIMEOUT_SECONDS=([0-9.]+)", env_str)
            if m_env:
                try:
                    timeout_s = float(m_env.group(1))
                except ValueError:
                    pass

        if timeout_s is None:
            timeout_s = 1.0  # Documented standard default

        timeout_ms = int(timeout_s * 1000)
        injected_latency_ms = max(2 * timeout_ms, 1500)
        jitter_ms = max(int(0.05 * injected_latency_ms), 50)
        return injected_latency_ms, jitter_ms

    def resolve_workload_target(self, compose_data: Dict[str, Any]) -> str:
        """Step 5: Resolve entrypoint service (root in depends_on graph or port 8000)."""
        services = compose_data.get("services", {})
        app_services = [s for s in services.keys() if s not in ("toxiproxy", "prometheus")]

        # Build reverse dependency map: who is depended on by whom?
        depended_on_by: Dict[str, List[str]] = {s: [] for s in app_services}
        for s_name in app_services:
            deps = services.get(s_name, {}).get("depends_on", [])
            if isinstance(deps, dict):
                deps = list(deps.keys())
            for d in deps:
                if d in depended_on_by:
                    depended_on_by[d].append(s_name)

        # Entry points have 0 inbound dependencies from other app services
        entrypoints = [s for s, in_deps in depended_on_by.items() if len(in_deps) == 0]
        if len(entrypoints) == 1:
            return entrypoints[0]

        # Prioritize service with port 8000 or 'frontend' / 'gateway' in name
        for ep in entrypoints or app_services:
            ports = services.get(ep, {}).get("ports", [])
            if any("8000" in str(p) for p in ports) or "frontend" in ep or "gateway" in ep:
                return ep

        return entrypoints[0] if entrypoints else app_services[0]

    def resolve_entrypoint_route(self, entrypoint_service: str, compose_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Resolves the active POST entrypoint route and payload from source route decorators."""
        ep_clean = _clean_service_name(entrypoint_service)
        source_paths = [
            f"app/{ep_clean}/main.py",
            f"app/{entrypoint_service}/main.py",
            f"{ep_clean}/main.py",
            f"src/{ep_clean}/main.py",
        ]
        
        found_route = "/orders"
        found_payload: Dict[str, Any] = {"item_id": "item_123", "quantity": 1}

        for p in source_paths:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                
                routes = re.findall(r'@app\.post\(\s*["\']([^"\']+)["\']', content)
                if routes:
                    biz_routes = [r for r in routes if r not in ("/health", "/metrics")]
                    if biz_routes:
                        found_route = biz_routes[0]
                        if "order" in found_route or "item" in found_route:
                            found_payload = {"item_id": "item_123", "quantity": 1}
                        elif "checkout" in found_route:
                            found_payload = {"order_id": "ord_123", "amount": 100.0, "currency": "USD"}
                        elif "reserve" in found_route:
                            found_payload = {"item_id": "item_123", "quantity": 1}
                break

        return found_route, found_payload
    def synthesize(
        self,
        pr_diff: str,
        case_id: str = "case-synthesized",
        git_commit: str = "main",
    ) -> Dict[str, Any]:
        """Step 6: Assemble full experiment specification dictionary."""
        compose_data = self._load_compose()
        
        changed_service = self.resolve_changed_service(pr_diff, compose_data)
        target_service, target_port = self.resolve_downstream_dependency(changed_service, compose_data, pr_diff)
        proxy_name, admin_url = self.resolve_fault_proxy(changed_service, target_service, target_port, compose_data)
        latency_ms, jitter_ms = self.resolve_fault_magnitude(pr_diff, compose_data, changed_service)
        workload_target = self.resolve_workload_target(compose_data)

        changed_short = _clean_service_name(changed_service)
        target_short = _clean_service_name(target_service)

        spec: Dict[str, Any] = {
            "id": case_id,
            "version": "1.1",
            "title": f"Topology-Synthesized: Downstream Latency Induces Retry Amplification ({changed_short} -> {target_short})",
            "description": (
                f"Automated synthesis: {changed_service} calls {target_service} over {proxy_name}. "
                f"Injected latency ({latency_ms}ms) calibrated against client timeout to reproduce retry storm."
            ),
            "target": {
                "compose_file": self.compose_path,
                "git_commit": git_commit,
            },
            "fault": {
                "tool": "toxiproxy",
                "proxy": proxy_name,
                "admin_url": admin_url,
                "toxic": {
                    "type": "latency",
                    "attributes": {
                        "latency": latency_ms,
                        "jitter": jitter_ms,
                    },
                },
            },
            "workload": {
                "target_service": workload_target,
                "tool": "k6",
                "script": "workloads/checkout_load.js",
                "duration": "45s",
                "vus": 10,
                "rps_target": 30,
            },
            "measurements": {
                "prometheus_url": "http://localhost:9090",
                "scrape_interval_s": 1,
                "metrics": [
                    {
                        "name": "retry_count_total",
                        "labels": {"service": changed_short, "target": target_short},
                    },
                    {
                        "name": "http_errors_total",
                        "labels": {"service": changed_short},
                    },
                    {
                        "name": f"{changed_short}_requests_total",
                        "labels": {"service": changed_short},
                    },
                ],
            },
            "assertions": {
                "pre_patch": [
                    {
                        "metric": "retries_per_request",
                        "condition": "> 2.0",
                        "description": f"Retry amplification storm visible as >2.0 retries per failed request on {changed_short}",
                    },
                    {
                        "metric": "total_requests",
                        "condition": ">= 100",
                        "description": "Sufficient workload request sample size under failure",
                    },
                ],
                "post_patch": [
                    {
                        "metric": "retries_per_request",
                        "condition": "<= 1.1",
                        "description": "Retry count bounded to <=1.1 retries per failed request after remediation",
                    },
                    {
                        "metric": "total_requests",
                        "condition": ">= 100",
                        "description": "Sufficient workload request sample size under failure",
                    },
                ],
            },
        }

        return spec

    def synthesize_and_save(
        self,
        pr_diff: str,
        output_path: str,
        case_id: str = "case-synthesized",
        git_commit: str = "main",
    ) -> Dict[str, Any]:
        """Synthesize spec and save to YAML file."""
        spec = self.synthesize(pr_diff=pr_diff, case_id=case_id, git_commit=git_commit)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(spec, f, sort_keys=False)
        return spec




