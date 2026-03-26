"""Main CLI entry point for p5."""
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
from p5.commands.edit    import edit_cmd     # noqa: E402
from p5.commands.add     import add_cmd      # noqa: E402
from p5.commands.delete  import delete_cmd   # noqa: E402
from p5.commands.sync    import sync_cmd     # noqa: E402
from p5.commands.change  import change_cmd   # noqa: E402
from p5.commands.submit  import submit_cmd   # noqa: E402
from p5.commands.changes import changes_cmd  # noqa: E402
from p5.commands.filelog import filelog_cmd  # noqa: E402

main.add_command(status_cmd,  "status")
main.add_command(diff_cmd,    "diff")
main.add_command(edit_cmd,    "edit")
main.add_command(add_cmd,     "add")
main.add_command(delete_cmd,  "delete")
main.add_command(sync_cmd,    "sync")
main.add_command(change_cmd,  "change")
main.add_command(submit_cmd,  "submit")
main.add_command(changes_cmd, "changes")
main.add_command(filelog_cmd, "filelog")
