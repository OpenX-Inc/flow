"""CLI entry point for Flow."""

import typer
from rich.console import Console

app = typer.Typer(
    name="flow",
    help="Flow — Open-source autonomous video generation pipeline.",
)
console = Console()


@app.command()
def generate(
    topic: str = typer.Option(..., help="Topic for video generation"),
    duration: int = typer.Option(60, help="Target video duration in seconds"),
    config_path: str = typer.Option("config/config.toml", help="Path to config file"),
    output: str = typer.Option("", help="Output file path (auto-generated if empty)"),
    dry_run: bool = typer.Option(
        False, help="Generate script only, skip GPU generation"
    ),
) -> None:
    """Generate a video from a topic."""
    import json

    from flow.config import load_config
    from flow.pipeline import Pipeline
    from flow.writer import Writer

    cfg = load_config(config_path)
    if output:
        cfg.output_dir = str(output)

    console.print(f"[bold green]Flow[/] — Generating video for: {topic}")
    console.print(f"  Duration: {duration}s | Aspect: {cfg.aspect_ratio}")

    if dry_run:
        console.print("  Mode: [yellow]dry-run[/] (script only, no GPU)")
        writer = Writer(cfg)
        shot_list = writer.generate(topic=topic, duration=duration)
        console.print(f"\n[bold]Title:[/] {shot_list.title}")
        console.print(f"[bold]Scenes:[/] {len(shot_list.scenes)}")
        console.print(f"[bold]Characters:[/] {list(shot_list.characters.keys())}")
        cost = len(shot_list.scenes) * 0.16
        time_est = len(shot_list.scenes) * 4.5
        console.print(
            f"\n[bold]Estimated cost:[/] ~${cost:.2f} (A100 480p)"
        )
        console.print(
            f"[bold]Estimated time:[/] ~{time_est:.0f} min (single A100)"
        )
        console.print("\n[bold]Shot list:[/]")
        console.print(json.dumps(shot_list.model_dump(), indent=2))
        return

    pipeline = Pipeline(cfg)
    result = pipeline.run(topic=topic, duration=duration)
    console.print(f"[bold green]✓[/] Video saved to: {result}")


@app.command()
def schedule(
    config_path: str = typer.Option("config/config.toml", help="Path to config file"),
) -> None:
    """Run the autonomous scheduler."""
    from flow.config import load_config
    from flow.scheduler import Scheduler

    cfg = load_config(config_path)
    console.print("[bold green]Flow[/] — Starting scheduler")
    scheduler = Scheduler(cfg)
    scheduler.run()


@app.command()
def agent(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8770, help="Bind port"),
) -> None:
    """Run the agentic video-editing API (kimi agent: /agent/chat, /models, /undo)."""
    from flow.api.app import run

    console.print(f"[bold green]Flow[/] — Agent API on http://{host}:{port}")
    console.print("  Endpoints: POST /agent/chat (SSE), GET /agent/models, POST /agent/undo")
    run(host=host, port=port)


@app.command()
def mcp(
    host: str = typer.Option("127.0.0.1", help="Bind host (loopback recommended)"),
    port: int = typer.Option(8765, help="Bind port"),
) -> None:
    """Run the MCP server exposing all tools to external agents (Claude Code/Cursor)."""
    from flow.mcp_server.server import run

    console.print(f"[bold green]Flow[/] — MCP server on http://{host}:{port}/mcp")
    console.print("  Set FLOW_MCP_TOKEN for bearer auth; "
                  "FLOW_MCP_PROJECT_ID for the active project")
    run(host=host, port=port)


@app.command()
def deploy(
    provider: str = typer.Argument(
        None, help="Target provider: modal | aws | gcp (default from config)"
    ),
    name: str = typer.Option(None, help="Instance name — deploy several, named"),
    gpu: str = typer.Option(None, help="GPU type, e.g. A100-80GB / H100"),
    model_t2v: str = typer.Option(None, help="T2V model id"),
    model_i2v: str = typer.Option(None, help="I2V model id"),
    region: str = typer.Option(None, help="Region (AWS/GCP)"),
    modal_token_id: str = typer.Option(
        None, help="Modal token id (else uses ambient modal auth / ~/.modal.toml)"
    ),
    modal_token_secret: str = typer.Option(
        None, help="Modal token secret (passed per-invocation, not via global env)"
    ),
    config_path: str = typer.Option("config/config.toml", help="Path to config file"),
) -> None:
    """Deploy the GPU backend to a provider as a named compute instance.

    A token alone can't generate — this deploys the open-source Wan backend into
    your account and reports the endpoint URL to register. CLI flags override the
    deploy section of your config file. Modal credentials may be passed as args
    (for unattended/multi-account deploys) or left to ambient modal auth.
    """
    from flow.config import load_config
    from flow.deploy import DeploySpec, available_providers, get_deployer

    d = load_config(config_path).deploy
    provider = provider or d.provider
    credentials: dict = {}
    if modal_token_id:
        credentials["token_id"] = modal_token_id
    if modal_token_secret:
        credentials["token_secret"] = modal_token_secret
    spec = DeploySpec(
        name=name or d.name,
        gpu=gpu or d.gpu,
        model_t2v=model_t2v or d.model_t2v,
        model_i2v=model_i2v or d.model_i2v,
        region=region or d.region,
        scaledown_window=d.scaledown_window,
        credentials=credentials,
    )

    try:
        deployer = get_deployer(provider)
    except ValueError:
        console.print(
            f"[red]Unknown provider '{provider}'[/] — "
            f"available: {', '.join(available_providers())}"
        )
        raise typer.Exit(1) from None

    console.print(
        f"[bold green]Flow[/] — deploying '{spec.name}' to "
        f"[cyan]{provider}[/] (gpu={spec.gpu})"
    )
    result = deployer.deploy(spec)

    if result.status == "deployed":
        console.print(f"[bold green]✓[/] deployed [bold]{result.name}[/]")
        if result.endpoint_url:
            console.print(f"  endpoint: [cyan]{result.endpoint_url}[/]")
        console.print(f"  {result.detail}")
    elif result.status == "manual_required":
        console.print(f"[yellow]⚠ manual steps required[/] for {provider}:")
        console.print(f"  {result.detail}")
    else:
        console.print(f"[red]✗ deploy failed:[/] {result.detail}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
