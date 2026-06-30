"""Tests for the GPU-backend deployers (no GPU / no cloud account needed)."""

from flow.deploy import DeploySpec, available_providers, get_deployer
from flow.deploy.modal_deploy import ModalDeployer


def test_providers_registered():
    assert set(available_providers()) >= {"modal", "aws", "gcp"}


def test_unknown_provider_raises():
    import pytest

    with pytest.raises(ValueError):
        get_deployer("nope")


def test_modal_server_module_is_packaged():
    # The deployer must be able to locate the GPU backend it deploys.
    path = ModalDeployer()._server_path()
    assert path.name == "modal_server.py"
    assert path.exists()


def test_modal_deploy_fails_cleanly_without_cli(monkeypatch):
    # No modal CLI installed -> honest failure, not a crash or fake success.
    monkeypatch.setattr("flow.deploy.modal_deploy.shutil.which", lambda _: None)
    res = ModalDeployer().deploy(DeploySpec(name="flow-gpu-test"))
    assert res.status == "failed"
    assert res.ok is False
    assert "modal CLI not found" in res.detail


def test_modal_deploy_injects_token_per_invocation(monkeypatch):
    """Credentials passed as args land in the subprocess env only, never os.environ."""
    import os
    import types

    monkeypatch.setattr(
        "flow.deploy.modal_deploy.shutil.which", lambda _: "/usr/bin/modal"
    )
    captured: dict = {}

    def fake_run(cmd, env=None, **kw):
        captured["env"] = env
        return types.SimpleNamespace(
            returncode=0,
            stdout="Created web endpoint => https://ws--a100.modal.run",
            stderr="",
        )

    monkeypatch.setattr("flow.deploy.modal_deploy.subprocess.run", fake_run)

    res = ModalDeployer().deploy(
        DeploySpec(name="a100", credentials={"token_id": "ti", "token_secret": "ts"})
    )

    assert res.status == "deployed"
    assert res.endpoint_url == "https://ws--a100.modal.run"
    # Token is scoped to the deploy subprocess...
    assert captured["env"]["MODAL_TOKEN_ID"] == "ti"
    assert captured["env"]["MODAL_TOKEN_SECRET"] == "ts"
    assert captured["env"]["FLOW_GPU_APP_NAME"] == "a100"
    # ...and never leaks into the ambient process env.
    assert "MODAL_TOKEN_ID" not in os.environ


def test_aws_gcp_are_honest_scaffolds():
    for provider in ("aws", "gcp"):
        res = get_deployer(provider).deploy(DeploySpec(name=f"{provider}-inst"))
        # Honest: declares manual steps, never claims a deployment happened.
        assert res.status == "manual_required"
        assert res.ok is False
        assert res.endpoint_url == ""
        assert "not automated yet" in res.detail
