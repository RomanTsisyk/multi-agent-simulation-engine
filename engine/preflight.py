"""Pre-flight environment checks for the wargame simulation.

Validates that all required services, files, and resources are available
before starting a potentially long game run.  Each check returns a
:class:`CheckResult` with pass/fail/warning status and a human-readable
message.

Usage::

    from engine.preflight import run_preflight_checks
    ok = run_preflight_checks(config)
    if not ok:
        sys.exit(1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ======================================================================
# Result types
# ======================================================================

@dataclass
class CheckResult:
    """Outcome of a single pre-flight check."""
    name: str
    status: str  # "PASS", "FAIL", "WARN"
    message: str
    critical: bool = True  # If True and status=="FAIL", abort the run


# ======================================================================
# Individual checks
# ======================================================================

def check_ollama_reachable(base_url: str) -> CheckResult:
    """Check that the Ollama API is reachable via HTTP."""
    import urllib.request
    import urllib.error

    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return CheckResult("Ollama reachable", "PASS", f"Connected to {base_url}")
            return CheckResult("Ollama reachable", "FAIL", f"HTTP {resp.status} from {url}", critical=True)
    except urllib.error.URLError as e:
        return CheckResult("Ollama reachable", "FAIL", f"Cannot connect to {base_url}: {e}", critical=True)
    except Exception as e:
        return CheckResult("Ollama reachable", "FAIL", f"Unexpected error: {e}", critical=True)


def check_model_available(base_url: str, model: str) -> CheckResult:
    """Check that the requested model is pulled in Ollama."""
    import json
    import urllib.request
    import urllib.error

    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        model_names = []
        for m in data.get("models", []):
            model_names.append(m.get("name", ""))
            # Also match without the :latest tag
            name_no_tag = m.get("name", "").split(":")[0]
            model_names.append(name_no_tag)

        if model in model_names:
            return CheckResult("Model available", "PASS", f"Model '{model}' found")

        # Check partial match (model name without tag)
        model_base = model.split(":")[0]
        if model_base in model_names:
            return CheckResult("Model available", "PASS", f"Model '{model}' found (base match)")

        available = ", ".join(sorted(set(m.get("name", "") for m in data.get("models", []))))
        return CheckResult(
            "Model available", "FAIL",
            f"Model '{model}' not found. Available: {available or 'none'}",
            critical=True,
        )
    except Exception as e:
        return CheckResult("Model available", "FAIL", f"Cannot check models: {e}", critical=True)


def check_ram_sufficient(base_url: str, model: str) -> CheckResult:
    """Heuristic RAM check based on model size."""
    import json
    import urllib.request

    try:
        url = f"{base_url.rstrip('/')}/api/show"
        payload = json.dumps({"name": model}).encode()
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        # Extract parameter size from model info
        details = data.get("details", {})
        param_size = details.get("parameter_size", "")

        # Parse parameter count for RAM estimate
        size_gb = 0
        if "b" in param_size.lower():
            try:
                num = float(param_size.lower().replace("b", "").strip())
                # Rough estimate: ~0.6 GB per billion params for Q4 quantization
                size_gb = num * 0.6
            except ValueError:
                pass

        if size_gb == 0:
            return CheckResult("RAM sufficient", "WARN", "Cannot estimate model RAM requirements", critical=False)

        # Check available RAM
        import shutil
        total_ram_gb = _get_total_ram_gb()
        if total_ram_gb > 0:
            if total_ram_gb < size_gb * 1.2:
                return CheckResult(
                    "RAM sufficient", "WARN",
                    f"Model needs ~{size_gb:.0f}GB, system has {total_ram_gb:.0f}GB total. May be tight.",
                    critical=False,
                )
            return CheckResult(
                "RAM sufficient", "PASS",
                f"Model needs ~{size_gb:.0f}GB, system has {total_ram_gb:.0f}GB total",
            )

        return CheckResult("RAM sufficient", "WARN", f"Model needs ~{size_gb:.0f}GB (cannot check system RAM)", critical=False)
    except Exception as e:
        return CheckResult("RAM sufficient", "WARN", f"Cannot estimate RAM: {e}", critical=False)


def check_country_files(countries_dir: Path) -> CheckResult:
    """Check that country YAML files exist."""
    if not countries_dir.exists():
        return CheckResult(
            "Country files", "FAIL",
            f"Countries directory not found: {countries_dir}",
            critical=True,
        )
    yaml_files = list(countries_dir.glob("*.yaml"))
    if not yaml_files:
        return CheckResult(
            "Country files", "FAIL",
            f"No YAML files in {countries_dir}",
            critical=True,
        )
    return CheckResult(
        "Country files", "PASS",
        f"Found {len(yaml_files)} country files in {countries_dir}",
    )


def check_num_ctx(num_ctx: int, num_countries: int) -> CheckResult:
    """Check if the context window is large enough for the number of countries."""
    recommended = 4000 + 1000 * num_countries
    if num_ctx >= recommended:
        return CheckResult(
            "Context window", "PASS",
            f"num_ctx={num_ctx} >= recommended {recommended} for {num_countries} countries",
        )
    return CheckResult(
        "Context window", "WARN",
        f"num_ctx={num_ctx} may be small for {num_countries} countries (recommended: {recommended})",
        critical=False,
    )


def check_scenario_file(scenario_path: Path) -> CheckResult:
    """Check that the scenario YAML file exists and is parseable."""
    if not scenario_path.exists():
        return CheckResult(
            "Scenario file", "FAIL",
            f"Scenario file not found: {scenario_path}",
            critical=True,
        )
    try:
        with open(scenario_path, "r") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return CheckResult(
                "Scenario file", "FAIL",
                f"Scenario file is not a valid YAML dict: {scenario_path}",
                critical=True,
            )
        name = data.get("name", "unnamed")
        return CheckResult(
            "Scenario file", "PASS",
            f"Scenario '{name}' loaded from {scenario_path}",
        )
    except yaml.YAMLError as e:
        return CheckResult(
            "Scenario file", "FAIL",
            f"YAML parse error in {scenario_path}: {e}",
            critical=True,
        )


def check_config_structure(raw_config: dict) -> CheckResult:
    """Validate that the config has all required top-level sections."""
    required = ["game", "llm"]
    missing = [k for k in required if k not in raw_config]
    if missing:
        return CheckResult(
            "Config structure", "FAIL",
            f"Missing required config sections: {', '.join(missing)}",
            critical=True,
        )

    # Check game section
    game = raw_config.get("game", {})
    if not game.get("scenario"):
        return CheckResult(
            "Config structure", "FAIL",
            "Config 'game' section missing 'scenario' path",
            critical=True,
        )

    # Check llm section
    llm = raw_config.get("llm", {})
    backend = llm.get("backend", "ollama")
    if backend not in llm:
        return CheckResult(
            "Config structure", "FAIL",
            f"Config 'llm' section missing '{backend}' backend settings",
            critical=True,
        )

    return CheckResult("Config structure", "PASS", "Config has all required sections")


# ======================================================================
# Main runner
# ======================================================================

def run_preflight_checks(
    raw_config: dict,
    project_root: Path,
    num_countries: int | None = None,
    skip_ollama: bool = False,
) -> bool:
    """Run all pre-flight checks and print results.

    Args:
        raw_config: The parsed config.yaml dictionary.
        project_root: Absolute path to the project root.
        num_countries: Number of countries to be loaded (for context window check).
        skip_ollama: If True, skip Ollama-specific checks (e.g. for deepseek backend).

    Returns:
        True if all critical checks passed, False otherwise.
    """
    results: list[CheckResult] = []

    # 1. Config structure
    results.append(check_config_structure(raw_config))

    llm_cfg = raw_config.get("llm", {})
    backend_name = llm_cfg.get("backend", "ollama")
    backend_cfg = llm_cfg.get(backend_name, {})

    # 2-3. Ollama-specific checks
    if backend_name == "ollama" and not skip_ollama:
        base_url = backend_cfg.get("base_url", "http://localhost:11434")
        model = backend_cfg.get("model", "")

        results.append(check_ollama_reachable(base_url))

        # Only check model if Ollama is reachable
        if results[-1].status == "PASS":
            results.append(check_model_available(base_url, model))
            results.append(check_ram_sufficient(base_url, model))

    # 4. Country files
    game_cfg = raw_config.get("game", {})
    countries_dir = project_root / game_cfg.get("countries_dir", "countries")
    results.append(check_country_files(countries_dir))

    # 5. Context window (only for Ollama)
    if backend_name == "ollama":
        num_ctx = backend_cfg.get("num_ctx", 8192)
        if num_countries is None:
            # Count from country files
            try:
                num_countries = len(list(countries_dir.glob("*.yaml")))
            except Exception:
                num_countries = 10
        results.append(check_num_ctx(num_ctx, num_countries))

    # 6. Scenario file
    scenario_rel = game_cfg.get("scenario", "scenarios/suwalki_gap.yaml")
    scenario_path = project_root / scenario_rel
    results.append(check_scenario_file(scenario_path))

    # Print results
    _print_results(results)

    # Check for critical failures
    critical_failures = [r for r in results if r.status == "FAIL" and r.critical]
    return len(critical_failures) == 0


def _print_results(results: list[CheckResult]) -> None:
    """Print check results as a formatted checklist."""
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()

        table = Table(title="Pre-flight Checks", show_header=True, header_style="bold")
        table.add_column("Status", width=6)
        table.add_column("Check", width=20)
        table.add_column("Details")

        for r in results:
            if r.status == "PASS":
                status = "[green][PASS][/green]"
            elif r.status == "WARN":
                status = "[yellow][WARN][/yellow]"
            else:
                status = "[bold red][FAIL][/bold red]"
            table.add_row(status, r.name, r.message)

        console.print(table)
    except ImportError:
        # Fallback: plain text
        print("\n--- Pre-flight Checks ---")
        for r in results:
            tag = f"[{r.status}]"
            print(f"  {tag:6s} {r.name}: {r.message}")
        print()


def _get_total_ram_gb() -> float:
    """Get total system RAM in GB (cross-platform)."""
    import platform
    import subprocess

    try:
        system = platform.system()
        if system == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            return int(result.stdout.strip()) / (1024 ** 3)
        elif system == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / (1024 ** 2)
    except Exception:
        pass
    return 0.0
