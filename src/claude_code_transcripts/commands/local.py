import shutil
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path

import click
import questionary

from claude_code_transcripts.cli import cli
from claude_code_transcripts.commands import local_options, source_option

from claude_code_transcripts.html_generation import (
    create_gist,
    generate_html,
    inject_gist_preview_js,
)
from claude_code_transcripts.parser import parse_session_file
from claude_code_transcripts.sessions import find_cowork_sessions, find_local_sessions


@cli.command("local")
@local_options
@source_option
def local_cmd(
    output, output_auto, repo, gist, include_json, open_browser, source, limit
):
    """Select and convert a local Claude Code or Cowork session to HTML."""
    click.echo("Loading local sessions...")

    sessions = []

    effective_limit = limit or 10

    if source != "cowork":
        code_folder = (
            Path.home() / ".claude" / "projects"
            if source in (None, "code")
            else Path(source)
        )
        if code_folder.exists():
            for filepath, summary in find_local_sessions(
                code_folder, limit=effective_limit
            ):
                stat = filepath.stat()
                sessions.append(
                    {
                        "mtime": stat.st_mtime,
                        "size_kb": stat.st_size / 1024,
                        "source": "Code",
                        "title": summary,
                        "session_file": filepath,
                        "transcript_label": "Claude Code",
                    }
                )

    if source in (None, "cowork") and len(sessions) < effective_limit:
        for session in find_cowork_sessions(limit=effective_limit - len(sessions)):
            jsonl_path = session["jsonl_path"]
            stat = jsonl_path.stat()
            sessions.append(
                {
                    "mtime": session["mtime"],
                    "size_kb": stat.st_size / 1024,
                    "source": "Cowork",
                    "title": session["title"],
                    "session_file": jsonl_path,
                    "transcript_label": "Claude Cowork",
                }
            )

    sessions.sort(key=lambda s: s["mtime"], reverse=True)
    sessions = sessions[:effective_limit]

    if not sessions:
        click.echo("No local sessions found.")
        return

    choices = []
    for session in sessions:
        mod_time = datetime.fromtimestamp(session["mtime"])
        date_str = mod_time.strftime("%Y-%m-%d %H:%M")
        title = session["title"]
        if len(title) > 50:
            title = title[:47] + "..."
        display = (
            f"{date_str}  {session['size_kb']:5.0f} KB  {session['source']:6}  {title}"
        )
        choices.append(questionary.Choice(title=display, value=session))

    selected = questionary.select(
        "Select a session to convert:",
        choices=choices,
    ).ask()

    if selected is None:
        click.echo("No session selected.")
        return

    session_file = selected["session_file"]
    transcript_label = selected["transcript_label"]

    auto_open = output is None and not gist and not output_auto
    if output_auto:
        parent_dir = Path(output) if output else Path(".")
        output = parent_dir / session_file.stem
    elif output is None:
        output = Path(tempfile.gettempdir()) / f"claude-session-{session_file.stem}"

    output = Path(output)
    generate_html(
        parse_session_file(session_file),
        output,
        github_repo=repo,
        transcript_label=transcript_label,
    )

    click.echo(f"Output: {output.resolve()}")

    if include_json:
        output.mkdir(exist_ok=True)
        json_dest = output / session_file.name
        shutil.copy(session_file, json_dest)
        json_size_kb = json_dest.stat().st_size / 1024
        click.echo(f"JSONL: {json_dest} ({json_size_kb:.1f} KB)")

    if gist:
        inject_gist_preview_js(output)
        click.echo("Creating GitHub gist...")
        gist_id, gist_url = create_gist(output)
        preview_url = f"https://gisthost.github.io/?{gist_id}/index.html"
        click.echo(f"Gist: {gist_url}")
        click.echo(f"Preview: {preview_url}")

    if open_browser or auto_open:
        index_url = (output / "index.html").resolve().as_uri()
        webbrowser.open(index_url)
