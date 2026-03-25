"""Shared Click option decorators for commands."""

import click


def output_options(func):
    """Apply the common output-related options to a command.

    Adds: --output, --json, --open
    """
    func = click.option(
        "--open",
        "open_browser",
        is_flag=True,
        help="Open the generated index.html in your default browser (default if no -o specified).",
    )(func)
    func = click.option(
        "--json",
        "include_json",
        is_flag=True,
        help="Include the original session file in the output directory.",
    )(func)
    func = click.option(
        "-o",
        "--output",
        type=click.Path(),
        help="Output directory. If not specified, writes to temp dir and opens in browser.",
    )(func)
    return func


def source_option(func):
    """Apply the --source option to a command."""
    return click.option(
        "-s",
        "--source",
        help=(
            "Session source: 'code' (default Code path), 'cowork' (Cowork sessions), "
            "or a path to a Claude projects directory. "
            "Omit to include both Code and Cowork."
        ),
    )(func)


def limit_option(func):
    """Apply the --limit option to a command."""
    return click.option(
        "--limit",
        default=None,
        type=int,
        help="Maximum number of sessions to show.",
    )(func)


def interactive_options(func):
    """Apply options shared by interactive single-session commands.

    Adds: --output, --json, --open, --output-auto, --gist, --repo
    """
    func = output_options(func)
    func = click.option(
        "--repo",
        help="GitHub repo (owner/name) for commit links.",
    )(func)
    func = click.option(
        "--gist",
        is_flag=True,
        help="Upload to GitHub Gist and output a gisthost.github.io URL.",
    )(func)
    func = click.option(
        "-a",
        "--output-auto",
        is_flag=True,
        help="Auto-name output subdirectory based on session filename (uses -o as parent, or current dir).",
    )(func)
    return func


def local_options(func):
    """Apply the full option set for the local session picker command.

    Adds: --output, --json, --open, --output-auto, --gist, --repo, --limit
    """
    func = limit_option(func)
    func = interactive_options(func)
    return func
