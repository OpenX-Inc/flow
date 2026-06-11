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
) -> None:
    """Generate a video from a topic."""
    from flow.config import load_config
    from flow.pipeline import Pipeline

    cfg = load_config(config_path)
    if output:
        cfg.output_dir = str(output)

    console.print(f"[bold green]Flow[/] — Generating video for: {topic}")
    console.print(f"  Duration: {duration}s | Aspect: {cfg.aspect_ratio}")

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


if __name__ == "__main__":
    app()
