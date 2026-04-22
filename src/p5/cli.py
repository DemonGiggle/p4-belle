"""Main CLI entry point for p5."""
from __future__ import annotations

import sys

import click
from rich.console import Console

from p5.dummy_data import render_completion
from p5.p4 import P4Error

console = Console()


class P5Group(click.Group):
    """Click group that catches P4Error and prints it cleanly."""

    def invoke(self, ctx: click.Context) -> None:
        try:
            return super().invoke(ctx)
        except P4Error as e:
            console.print(f"[red]error:[/red] {e}")
            sys.exit(1)


@click.group(cls=P5Group, context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """p5 — Perforce with git-like UX.\n
    Wraps p4 commands with relative paths, colored output, and a better interface.
    """


# Import and register all commands
from p5.commands.status  import status_cmd   # noqa: E402
from p5.commands.diff    import diff_cmd     # noqa: E402
from p5.commands.delete  import delete_cmd   # noqa: E402
from p5.commands.sync    import sync_cmd     # noqa: E402
from p5.commands.change  import change_cmd   # noqa: E402
from p5.commands.submit  import submit_cmd   # noqa: E402
from p5.commands.changes import changes_cmd  # noqa: E402
from p5.commands.filelog import filelog_cmd  # noqa: E402
from p5.commands.ws      import ws_cmd       # noqa: E402

main.add_command(status_cmd,  "status")
main.add_command(diff_cmd,    "diff")
main.add_command(delete_cmd,  "delete")
main.add_command(sync_cmd,    "sync")
main.add_command(change_cmd,  "change")
main.add_command(submit_cmd,  "submit")
main.add_command(changes_cmd, "changes")
main.add_command(filelog_cmd, "filelog")
main.add_command(ws_cmd,      "ws")


_COMPLETION_SCRIPTS = {
    "bash": 'eval "$(_P5_COMPLETE=bash_source p5)"',
    "zsh":  'eval "$(_P5_COMPLETE=zsh_source p5)"',
    "fish": '_P5_COMPLETE=fish_source p5 | source',
}

_COMPLETION_PROFILES = {
    "bash": "~/.bashrc",
    "zsh":  "~/.zshrc",
    "fish": "~/.config/fish/config.fish",
}


@main.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]), default=None, required=False)
@click.option("--install", is_flag=True, help="Append completion line to your shell profile")
@click.option("--dummy-data", is_flag=True,
              help="Display sample output instead of changing shell config")
def completion_cmd(shell: str | None, install: bool, dummy_data: bool) -> None:
    """Print shell completion setup instructions (or install with --install).

    Auto-detects your shell from $SHELL, or pass bash/zsh/fish explicitly.

    \b
    Examples:
      p5 completion            # show instructions for current shell
      p5 completion zsh        # show instructions for zsh
      p5 completion --install  # append to ~/.bashrc (or ~/.zshrc etc.)
    """
    if dummy_data:
        render_completion(shell, install)
        return

    import os
    from pathlib import Path

    if shell is None:
        shell_bin = os.environ.get("SHELL", "")
        for s in ("bash", "zsh", "fish"):
            if s in shell_bin:
                shell = s
                break
        else:
            shell = "bash"

    script  = _COMPLETION_SCRIPTS[shell]
    profile = Path(_COMPLETION_PROFILES[shell]).expanduser()

    if install:
        marker = "_P5_COMPLETE"
        # Check if already installed
        if profile.exists() and marker in profile.read_text():
            console.print(f"[dim]Already installed in {profile}[/dim]")
            return
        with profile.open("a") as f:
            f.write(f"\n# p5 shell completion\n{script}\n")
        console.print(f"[green]✓[/green] Appended to [cyan]{profile}[/cyan]")
        console.print(f"[dim]Run: source {profile}[/dim]")
        return

    console.print(f"\n[bold]Enable p5 tab completion for {shell}[/bold]\n")
    console.print(f"Add this line to [cyan]{profile}[/cyan]:\n")
    console.print(f"  [green]{script}[/green]\n")
    console.print(f"Or install automatically:\n")
    console.print(f"  [dim]p5 completion {shell} --install[/dim]\n")
    console.print(f"[dim]Then restart your shell or run: source {profile}[/dim]\n")
