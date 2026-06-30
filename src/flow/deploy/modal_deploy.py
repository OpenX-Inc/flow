"""Modal deployer — runs ``modal deploy`` on the GPU backend as a named app.

Real and automated: validates the modal CLI, passes the spec through as env
(read by ``gpu_backend/modal_server.py`` at deploy time), runs the deploy, and
reports the resulting ``*.modal.run`` base URL.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from flow.deploy.base import Deployer, DeployResult, DeploySpec, register

_MODAL_URL = re.compile(r"https://[^\s\"']+\.modal\.run")


@register
class ModalDeployer(Deployer):
    provider = "modal"

    def _server_path(self) -> Path:
        """Locate the packaged GPU backend module (works installed or in-repo)."""
        import gpu_backend

        return Path(gpu_backend.__file__).parent / "modal_server.py"

    def deploy(self, spec: DeploySpec) -> DeployResult:
        if shutil.which("modal") is None:
            return DeployResult(
                spec.name, self.provider, "failed",
                detail="modal CLI not found. Install + auth: "
                "`pip install modal && modal token new`.",
            )
        server = self._server_path()
        if not server.exists():
            return DeployResult(
                spec.name, self.provider, "failed",
                detail=f"GPU backend module not found at {server}",
            )

        env = {
            **os.environ,
            "FLOW_GPU_APP_NAME": spec.name,
            "FLOW_GPU_TYPE": spec.gpu,
            "FLOW_MODEL_T2V": spec.model_t2v,
            "FLOW_MODEL_I2V": spec.model_i2v,
            "FLOW_GPU_SCALEDOWN": str(spec.scaledown_window),
        }
        # Per-invocation Modal auth, if provided as args, scoped to THIS
        # subprocess only (never the ambient env) — so a shared host can deploy
        # for many accounts concurrently. If omitted, ambient modal auth
        # (~/.modal.toml or existing MODAL_TOKEN_* env) is used as before.
        creds = spec.credentials or {}
        if creds.get("token_id"):
            env["MODAL_TOKEN_ID"] = creds["token_id"]
        if creds.get("token_secret"):
            env["MODAL_TOKEN_SECRET"] = creds["token_secret"]

        try:
            proc = subprocess.run(
                ["modal", "deploy", str(server)],
                env=env, capture_output=True, text=True, timeout=1800,
            )
        except (subprocess.TimeoutExpired, OSError) as err:
            return DeployResult(spec.name, self.provider, "failed", detail=str(err))

        combined = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            return DeployResult(
                spec.name, self.provider, "failed",
                detail=combined.strip()[-800:] or "modal deploy failed",
            )

        urls = _MODAL_URL.findall(combined)
        url = urls[0] if urls else ""
        return DeployResult(
            spec.name, self.provider, "deployed", endpoint_url=url,
            detail=(
                "Deployed. Register this base URL as a named compute instance."
                if url else
                "Deployed; run `modal app list` to find the base URL."
            ),
        )
