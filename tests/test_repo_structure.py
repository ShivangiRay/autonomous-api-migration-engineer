from pathlib import Path


def test_python_packages_use_importable_directory_names() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    assert not (repo_root / "apps" / "api-orchestrator").exists()
    assert (repo_root / "apps" / "api_orchestrator" / "main.py").exists()
    assert not (repo_root / "agents" / "contract-generator").exists()
    assert (repo_root / "agents" / "contract_generator" / "agent.py").exists()

