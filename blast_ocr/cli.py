"""
blast_ocr.cli

Production Command Line Interface for B.L.A.S.T. OCR Protocol.
Provides rich terminal feedback, progress bars, formatting options,
engine switching, and automated document ingestion.
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
    console = Console()
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False

from blast_ocr.pipeline import BlastPipeline
from blast_ocr.core.engines import _ENGINE_REGISTRY


def run_cli():
    parser = argparse.ArgumentParser(
        prog="blast-ocr",
        description="🚀 B.L.A.S.T. Production OCR Engine -- High-Fidelity Document & Book Digitization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  blast-ocr scan.pdf --out results/
  blast-ocr pages/ --engine ensemble --dewarp --out book_out/
  blast-ocr document.png --secure-mode --formats md,docx,pdf
  blast-ocr --serve --port 8000
        """,
    )

    parser.add_argument("source", nargs="?", help="Path to input document (PDF, PPTX, image, or image folder)")
    parser.add_argument("--out", "-o", help="Output directory for generated artifacts", default=None)
    parser.add_argument("--engine", "-e", choices=list(_ENGINE_REGISTRY.keys()), default="rapidocr", help="OCR Engine (default: rapidocr)")
    parser.add_argument("--formats", "-f", default="md,docx,pdf,txt,epub,json", help="Comma-separated formats (default: all)")
    parser.add_argument("--dewarp", action="store_true", help="Enable book spine curvature dewarping")
    parser.add_argument("--denoise", type=int, default=0, help="Denoising filter level (0-20, default: 0)")
    parser.add_argument("--contrast", type=float, default=1.0, help="Contrast boost multiplier (default: 1.0)")
    parser.add_argument("--no-deskew", action="store_true", help="Disable automatic skew angle correction")
    parser.add_argument("--no-tier0", action="store_true", help="Disable native PDF vector text extraction")
    parser.add_argument("--secure-mode", action="store_true", help="Enable enterprise PII redaction (SSN, cards, emails, tokens)")
    parser.add_argument("--workers", "-w", type=int, default=2, help="Number of parallel OCR worker threads (default: 2)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON summary to stdout")
    parser.add_argument("--serve", action="store_true", help="Launch FastAPI REST API server instead of batch processing")
    # 0.0.0.0 default is required for container port binding & Docker ingress
    parser.add_argument("--host", default="0.0.0.0", help="API host (used with --serve, default: 0.0.0.0)")  # nosec B104
    parser.add_argument("--port", type=int, default=8000, help="API port (used with --serve, default: 8000)")

    args = parser.parse_args()

    # REST Server mode
    if args.serve:
        from blast_ocr.api.server import start_server
        start_server(host=args.host, port=args.port)
        return 0

    if not args.source:
        parser.print_help()
        return 1

    source_path = str(Path(args.source).resolve())
    if not os.path.exists(source_path):
        if HAS_RICH and console:
            console.print(f"[bold red]Error:[/bold red] Source path '{source_path}' does not exist.")
        else:
            print(f"Error: Source path '{source_path}' does not exist.", file=sys.stderr)
        return 1

    config_overrides = {
        "ocr_engine": args.engine,
        "auto_deskew": not args.no_deskew,
        "denoise_level": args.denoise,
        "contrast_boost": args.contrast,
        "enable_dewarp": args.dewarp,
        "enable_tier0_routing": not args.no_tier0,
        "secure_mode": args.secure_mode,
        "max_workers": args.workers,
        "output_dir": args.out,
    }

    if HAS_RICH and console and not args.json:
        console.print(Panel.fit(
            f"[bold gold1]B.L.A.S.T. OCR Production Engine[/bold gold1] v3.0.0\n"
            f"[dim]Source:[/dim] [cyan]{source_path}[/cyan]\n"
            f"[dim]Engine:[/dim] [green]{args.engine}[/green] | "
            f"[dim]Workers:[/dim] {args.workers} | "
            f"[dim]Secure Mode:[/dim] {'[red]ON[/red]' if args.secure_mode else '[dim]OFF[/dim]'}",
            border_style="yellow",
        ))

    pipeline = BlastPipeline(config_overrides=config_overrides)
    start_time = time.monotonic()

    try:
        if HAS_RICH and console and not args.json:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                p_task = progress.add_task("[yellow]Processing document...", total=100)

                def progress_cb(current, total):
                    if total > 0:
                        pct = (current / total) * 100.0
                        progress.update(p_task, completed=pct, description=f"[yellow]Page {current}/{total}...")

                result = pipeline.process_job(source_path, output_dir=args.out, progress_callback=progress_cb)
                progress.update(p_task, completed=100, description="[green]Processing complete!")
        else:
            result = pipeline.process_job(source_path, output_dir=args.out)

        elapsed = time.monotonic() - start_time

        if args.json:
            print(json.dumps(result, indent=2))
        elif HAS_RICH and console:
            table = Table(title="Generated Artifacts", border_style="dim")
            table.add_column("Format", style="cyan bold")
            table.add_column("Location", style="white")

            gen_files = result.get("generated_files", {})
            for fmt, path in gen_files.items():
                if path:
                    table.add_row(fmt.upper(), str(path))

            console.print(table)
            meta = result.get("metadata", {})
            console.print(f"[bold green]✓ SUCCESS[/bold green] in {elapsed:.2f}s | Pages: {meta.get('page_count', 1)}")
        else:
            print(f"Status: {result.get('status')}")
            print(f"Generated files: {json.dumps(result.get('generated_files'), indent=2)}")

        return 0 if result.get("status") == "success" else 1

    except Exception as e:
        if HAS_RICH and console and not args.json:
            console.print(f"[bold red]Pipeline Error:[/bold red] {e}")
        else:
            print(f"Pipeline Error: {e}", file=sys.stderr)
        return 1
    finally:
        pipeline.close()


if __name__ == "__main__":
    sys.exit(run_cli())
