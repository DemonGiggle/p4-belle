"""Main CLI entry point for p5."""
from __future__ import annotations

import click
from rich.console import Console

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
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
def completion_cmd(shell: str | None) -> None:
    """Print shell completion setup instructions.

    Run the printed line (or add it to your shell profile) to enable tab
    completion for all p5 commands and arguments.

    \b
    Examples:
      p5 completion bash   # bash instructions
      p5 completion zsh    # zsh instructions
      p5 completion fish   # fish instructions
    """
    import os
    if shell is None:
        # Auto-detect from $SHELL
        shell_bin = os.environ.get("SHELL", "")
        for s in ("bash", "zsh", "fish"):
            if s in shell_bin:
                shell = s
                break
        else:
            shell = "bash"

    script  = _COMPLETION_SCRIPTS[shell]
    profile = _COMPLETION_PROFILES[shell]

    console.print(f"\n[bold]Enable p5 tab completion for {shell}[/bold]\n")
    console.print(f"Add this line to [cyan]{profile}[/cyan]:\n")
    console.print(f"  [green]{script}[/green]\n")
    console.print(f"Or run it now in your current shell:\n")
    console.print(f"  [dim]{script}[/dim]\n")
    console.print("[dim]Then restart your shell or run: source " + profile + "[/dim]\n")
