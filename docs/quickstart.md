# Quickstart

Install Helix in editable mode:

```bash
pip install -e ".[dev]"
```

Run the local deterministic workflow:

```bash
helix baseline workflows/demo_chain.yaml
helix run workflows/demo_chain.yaml
helix bench workflows/demo_chain.yaml
```

The fake backend requires no API keys and produces stable SHA-256 responses for repeatable benchmarks.

