import shutil
import webbrowser
from pathlib import Path

import click
import questionary

from claude_code_transcripts.cli import cli
from claude_code_transcripts.commands import output_options, source_option
from claude_code_transcripts.html_generation import (
    Project,
    Session,
    generate_batch_html,
)
from claude_code_transcripts.parser import parse_session_file
from claude_code_transcripts.sessions import find_all_sessions, find_cowork_sessions


@cli.command("project")
@output_options
@source_option
def project_cmd(output, include_json, open_browser, source):
    """Select a project and convert all its sessions to a browsable HTML archive."""
    raw_projects = []

    if source != "cowork":
        code_folder = (
            Path.home() / ".claude" / "projects"
            if source in (None, "code")
            else Path(source)
        )
        if not code_folder.exists():
            raise click.ClickException(f"Source directory not found: {code_folder}")
        raw_projects = find_all_sessions(code_folder)

    if source in (None, "cowork"):
        raw_cowork = find_cowork_sessions()
        if raw_cowork:
            cowork_sessions = []
            for session in raw_cowork:
                jsonl_path = session["jsonl_path"]
                stat = jsonl_path.stat()
                cowork_sessions.append(
                    {
                        "path": jsonl_path,
                        "summary": session["title"],
                        "mtime": session["mtime"],
                        "size": stat.st_size,
                        "transcript_label": "Claude Cowork",
                    }
                )
            raw_projects.append(
                {
                    "name": "Cowork",
                    "sessions": cowork_sessions,
                }
            )

    if not raw_projects:
        click.echo("No projects found.")
        return

    choices = [
        questionary.Choice(
            title=f"{p['name']}  ({len(p['sessions'])} session{'s' if len(p['sessions']) != 1 else ''})",
            value=p,
        )
        for p in raw_projects
    ]

    selected = questionary.select("Select a project to convert:", choices=choices).ask()

    if selected is None:
        click.echo("No project selected.")
        return

    output = Path(output) if output else Path("./claude-archive")
    project_dir = output / selected["name"]

    sessions = []
    for raw_session in selected["sessions"]:
        session_name = raw_session["path"].stem
        session_dir = project_dir / session_name
        loglines = parse_session_file(raw_session["path"])
        sessions.append(
            Session(
                name=session_name,
                session_dir=session_dir,
                loglines=loglines,
                size_kb=raw_session["size"] / 1024,
                transcript_label=raw_session.get("transcript_label", "Claude Code"),
            )
        )

    projects = [
        Project(name=selected["name"], project_dir=project_dir, sessions=sessions)
    ]

    click.echo(f"Generating archive in {output}...")
    stats = generate_batch_html(projects, output)

    if include_json:
        for raw_session in selected["sessions"]:
            session_name = raw_session["path"].stem
            session_dir = project_dir / session_name
            shutil.copy(raw_session["path"], session_dir / raw_session["path"].name)

    if stats["failed_sessions"]:
        click.echo(f"\nWarning: {len(stats['failed_sessions'])} session(s) failed:")
        for failure in stats["failed_sessions"]:
            click.echo(
                f"  {failure['project']}/{failure['session']}: {failure['error']}"
            )

    click.echo(
        f"Generated archive with {stats['total_sessions']} session(s) "
        f"from project '{selected['name']}'"
    )
    click.echo(f"Output: {output.resolve()}")

    if open_browser:
        index_url = (project_dir / "index.html").resolve().as_uri()
        webbrowser.open(index_url)
