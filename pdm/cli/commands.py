import os
import shutil
import subprocess

import click
from click._compat import term_len
from click.formatting import measure_table, iter_rows, wrap_text, HelpFormatter

from pdm.cli import actions
from pdm.cli.options import (
    dry_run_option,
    save_strategy_option,
    sections_option,
    verbose_option,
    update_strategy_option,
)
from pdm.context import context
from pdm.exceptions import CommandNotFound
from pdm.project import Project

pass_project = click.make_pass_decorator(Project, ensure=True)
context_settings = {"ignore_unknown_options": True, "allow_extra_args": True}


class ColoredHelpFormatter(HelpFormatter):
    """Click does not provide possibility to replace the inner formatter class
    easily, we have to use monkey patch technique.
    """

    def write_heading(self, heading):
        super().write_heading(context.io.yellow(heading, bold=True))

    def write_dl(self, rows, col_max=30, col_spacing=2):
        rows = list(rows)
        widths = measure_table(rows)
        if len(widths) != 2:
            raise TypeError("Expected two columns for definition list")

        first_col = min(widths[0], col_max) + col_spacing

        for first, second in iter_rows(rows, len(widths)):
            self.write("%*s%s" % (self.current_indent, "", context.io.cyan(first)))
            if not second:
                self.write("\n")
                continue
            if term_len(first) <= first_col - col_spacing:
                self.write(" " * (first_col - term_len(first)))
            else:
                self.write("\n")
                self.write(" " * (first_col + self.current_indent))

            text_width = max(self.width - first_col - 2, 10)
            lines = iter(wrap_text(second, text_width).splitlines())
            if lines:
                self.write(next(lines) + "\n")
                for line in lines:
                    self.write("%*s%s\n" % (first_col + self.current_indent, "", line))
            else:
                self.write("\n")


click.core.HelpFormatter = ColoredHelpFormatter


@click.group(help="PDM - Python Development Master")
@verbose_option
@click.version_option(
    prog_name=context.io._style("pdm", bold=True), version=context.version
)
def cli():
    pass


@cli.command(help="Lock dependencies.")
@verbose_option
@pass_project
def lock(project):
    actions.do_lock(project)


@cli.command(help="Install dependencies from lock file.")
@verbose_option
@sections_option
@click.option(
    "--no-lock",
    "lock",
    flag_value=False,
    default=True,
    help="Don't do lock if lockfile is not found or outdated.",
)
@pass_project
def install(project, sections, dev, default, lock):
    if lock and not (
        project.lockfile_file.is_file() and project.is_lockfile_hash_match()
    ):
        actions.do_lock(project)
    actions.do_sync(project, sections, dev, default, False, False)


@cli.command(
    help="Run commands or scripts with local packages loaded.",
    context_settings=context_settings,
)
@verbose_option
@click.argument("command")
@click.argument("args", nargs=-1)
@pass_project
def run(project, command, args):
    with project.environment.activate():
        expanded_command = shutil.which(command, path=os.getenv("PATH"))
        if not expanded_command:
            raise CommandNotFound(command)
        subprocess.run([expanded_command] + list(args))


@cli.command(help="Synchronizes current working set with lock file.")
@verbose_option
@sections_option
@dry_run_option
@click.option(
    "--clean/--no-clean",
    "clean",
    default=None,
    help="Whether to remove unneeded packages from working set.",
)
@pass_project
def sync(project, sections, dev, default, dry_run, clean):
    actions.do_sync(project, sections, dev, default, dry_run, clean)


@cli.command(help="Add packages to pyproject.toml and install them.")
@verbose_option
@click.option(
    "-d",
    "--dev",
    default=False,
    is_flag=True,
    help="Add packages into dev dependencies.",
)
@click.option("-s", "--section", help="Specify target section to add into.")
@click.option(
    "--no-sync",
    "sync",
    flag_value=False,
    default=True,
    help="Only write pyproject.toml and do not sync the working set.",
)
@save_strategy_option
@update_strategy_option
@click.option(
    "-e",
    "editables",
    multiple=True,
    help="Specify editable packages.",
    metavar="EDITABLES",
)
@click.argument("packages", nargs=-1)
@pass_project
def add(project, dev, section, sync, save, strategy, editables, packages):
    actions.do_add(project, dev, section, sync, save, strategy, editables, packages)


@cli.command(help="Update packages in pyproject.toml")
@verbose_option
@sections_option
@update_strategy_option
@click.argument("packages", nargs=-1)
@pass_project
def update(project, dev, sections, default, strategy, packages):
    actions.do_update(project, dev, sections, default, strategy, packages)


@cli.command(help="Remove packages from pyproject.toml")
@verbose_option
@click.option(
    "-d",
    "--dev",
    default=False,
    is_flag=True,
    help="Remove packages from dev dependencies.",
)
@click.option("-s", "--section", help="Specify target section the package belongs to")
@click.option(
    "--no-sync",
    "sync",
    flag_value=False,
    default=True,
    help="Only write pyproject.toml and do not uninstall packages.",
)
@click.argument("packages", nargs=-1)
@pass_project
def remove(project, dev, section, sync, packages):
    actions.do_remove(project, dev, section, sync, packages)


@cli.command(name="list", help="List packages installed in current working set.")
@verbose_option
@pass_project
def list_(project):
    actions.do_list(project)


@cli.command(help="Build artifacts for distribution.")
@verbose_option
@click.option(
    "--no-sdist",
    "sdist",
    default=True,
    flag_value=False,
    help="Don't build source tarballs.",
)
@click.option(
    "--no-wheel", "wheel", default=True, flag_value=False, help="Don't build wheels."
)
@click.option("-d", "--dest", default="dist", help="Target directory to put artifacts.")
@pass_project
def build(project, sdist, wheel, dest):
    actions.do_build(project, sdist, wheel, dest)