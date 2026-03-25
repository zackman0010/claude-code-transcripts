import shutil
import webbrowser
from datetime import datetime
from pathlib import Path

import click

from claude_code_transcripts.cli import cli

from claude_code_transcripts.html_generation import (
    Project,
    Session,
    generate_batch_html,
)
from claude_code_transcripts.commands import output_options, source_option
from claude_code_transcripts.parser import parse_session_file
from claude_code_transcripts.sessions import find_all_sessions, find_cowork_sessions


@cli.command("all")
@output_options
@source_option
@click.option(
    "--include-agents",
    is_flag=True,
    help="Include agent-* session files (excluded by default).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be converted without creating files.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Suppress all output except errors.",
)
def all_cmd(output, include_json, open_browser, source, include_agents, dry_run, quiet):
    """Convert all local Claude Code sessions to a browsable HTML archive.

    Creates a directory structure with:
    - Master index listing all projects
    - Per-project pages listing sessions
    - Individual session transcripts
    """
    output = Path(output) if output else Path("./claude-archive")
    raw_projects = []

    if source != "cowork":
        code_folder = (
            Path.home() / ".claude" / "projects"
            if source in (None, "code")
            else Path(source)
        )
        if not code_folder.exists():
            raise click.ClickException(f"Source directory not found: {code_folder}")
        if not quiet:
            click.echo(f"Scanning {code_folder}...")
        raw_projects = find_all_sessions(code_folder, include_agents=include_agents)

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
        if not quiet:
            click.echo("No sessions found.")
        return

    total_sessions = sum(len(p["sessions"]) for p in raw_projects)

    if not quiet:
        click.echo(f"Found {len(raw_projects)} projects with {total_sessions} sessions")

    if dry_run:
        if not quiet:
            click.echo("\nDry run - would convert:")
            for project in raw_projects:
                click.echo(
                    f"\n  {project['name']} ({len(project['sessions'])} sessions)"
                )
                for session in project["sessions"][:3]:
                    mod_time = datetime.fromtimestamp(session["mtime"])
                    click.echo(
                        f"    - {session['path'].stem} ({mod_time.strftime('%Y-%m-%d')})"
                    )
                if len(project["sessions"]) > 3:
                    click.echo(f"    ... and {len(project['sessions']) - 3} more")
        return

    if not quiet:
        click.echo(f"\nParsing sessions...")

    projects = []
    for raw_project in raw_projects:
        project_dir = output / raw_project["name"]
        sessions = []
        for raw_session in raw_project["sessions"]:
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
        projects.append(
            Project(
                name=raw_project["name"], project_dir=project_dir, sessions=sessions
            )
        )

    if not quiet:
        click.echo(f"Generating archive in {output}...")

    def on_progress(project_name, session_name, current, total):
        if not quiet and current % 10 == 0:
            click.echo(f"  Processed {current}/{total} sessions...")

    stats = generate_batch_html(
        projects,
        output,
        progress_callback=on_progress,
    )

    if include_json:
        for raw_project in raw_projects:
            for raw_session in raw_project["sessions"]:
                session_name = raw_session["path"].stem
                session_dir = output / raw_project["name"] / session_name
                json_dest = session_dir / raw_session["path"].name
                shutil.copy(raw_session["path"], json_dest)

    if stats["failed_sessions"]:
        click.echo(f"\nWarning: {len(stats['failed_sessions'])} session(s) failed:")
        for failure in stats["failed_sessions"]:
            click.echo(
                f"  {failure['project']}/{failure['session']}: {failure['error']}"
            )

    if not quiet:
        click.echo(
            f"\nGenerated archive with {stats['total_projects']} projects, "
            f"{stats['total_sessions']} sessions"
        )
        click.echo(f"Output: {output.resolve()}")

    if open_browser:
        index_url = (output / "index.html").resolve().as_uri()
        webbrowser.open(index_url)
