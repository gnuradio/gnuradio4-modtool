"""gr4_modtool CLI entry point."""

from __future__ import annotations

import sys

import click

from gr4_modtool import plugins as _plugins
from gr4_modtool.commands.add_dep import cmd as add_dep_cmd
from gr4_modtool.commands.add_test import cmd as add_test_cmd
from gr4_modtool.commands.build import cmd as build_cmd
from gr4_modtool.commands.check import cmd as check_cmd
from gr4_modtool.commands.ci import cmd as ci_cmd
from gr4_modtool.commands.completion import cmd as completion_cmd
from gr4_modtool.commands.coverage import cmd as coverage_cmd
from gr4_modtool.commands.cp import cmd as cp_cmd
from gr4_modtool.commands.devcontainer import cmd as devcontainer_cmd
from gr4_modtool.commands.docs import cmd as docs_cmd
from gr4_modtool.commands.doctor import cmd as doctor_cmd
from gr4_modtool.commands.export_spec import cmd as export_spec_cmd
from gr4_modtool.commands.format import cmd as format_cmd
from gr4_modtool.commands.info import cmd as info_cmd
from gr4_modtool.commands.init import cmd as init_cmd
from gr4_modtool.commands.lint_headers import cmd as lint_headers_cmd
from gr4_modtool.commands.ls import cmd as ls_cmd
from gr4_modtool.commands.mv import cmd as mv_cmd
from gr4_modtool.commands.newbench import cmd as newbench_cmd
from gr4_modtool.commands.newblock import cmd as newblock_cmd
from gr4_modtool.commands.newgroup import cmd as newgroup_cmd
from gr4_modtool.commands.newmod import cmd as newmod_cmd
from gr4_modtool.commands.newparam import cmd as newparam_cmd
from gr4_modtool.commands.port import cmd as port_cmd
from gr4_modtool.commands.precommit import cmd as precommit_cmd
from gr4_modtool.commands.publish import cmd as publish_cmd
from gr4_modtool.commands.rename import cmd as rename_cmd
from gr4_modtool.commands.rename_block import cmd as rename_block_cmd
from gr4_modtool.commands.rename_group import cmd as rename_group_cmd
from gr4_modtool.commands.rm import cmd as rm_cmd
from gr4_modtool.commands.run_test import cmd as test_cmd
from gr4_modtool.commands.sanitizers import cmd as presets_cmd
from gr4_modtool.commands.search import cmd as search_cmd
from gr4_modtool.commands.show import cmd as show_cmd
from gr4_modtool.commands.status import cmd as status_cmd
from gr4_modtool.commands.sync import cmd as sync_cmd
from gr4_modtool.commands.templates import cmd as templates_cmd
from gr4_modtool.commands.tidy import cmd as tidy_cmd
from gr4_modtool.commands.validate import cmd as validate_cmd
from gr4_modtool.commands.version_bump import cmd as version_bump_cmd
from gr4_modtool.commands.vscode import cmd as vscode_cmd
from gr4_modtool.log import ENV_FILE, configure_logging, get_logger

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

log = get_logger(__name__)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Log what the tool is doing: -v for progress, -vv for debug detail.",
)
@click.option("-q", "--quiet", is_flag=True, help="Log errors only.")
@click.option(
    "--log-file",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    envvar=ENV_FILE,
    help=f"Append a full debug log to this file (env: {ENV_FILE}).",
)
@click.version_option()
@click.pass_context
def cli(ctx: click.Context, verbose: int, quiet: bool, log_file: str | None) -> None:
    """GNURadio 4 OOT module management tool.

    Logging: -v shows every file written and command run, -vv adds debug detail,
    and --log-file records everything regardless of the console level. The
    console level also honours $GR4_MODTOOL_LOG_LEVEL.
    """
    if quiet and verbose:
        raise click.UsageError("--quiet and --verbose are mutually exclusive")
    configure_logging(verbose=verbose, quiet=quiet, log_file=log_file)
    ctx.obj = {"verbose": verbose, "quiet": quiet, "log_file": log_file}
    if ctx.invoked_subcommand:
        log.debug("gr4_modtool %s", " ".join(sys.argv[1:]))


cli.add_command(newmod_cmd, name="newmod")
cli.add_command(newgroup_cmd, name="newgroup")
cli.add_command(newblock_cmd, name="newblock")
cli.add_command(rm_cmd, name="rm")
cli.add_command(rename_cmd, name="rename")
cli.add_command(rename_block_cmd, name="rename-block")
cli.add_command(rename_group_cmd, name="rename-group")
cli.add_command(status_cmd, name="status")
cli.add_command(info_cmd, name="info")
cli.add_command(init_cmd, name="init")
cli.add_command(check_cmd, name="check")
cli.add_command(mv_cmd, name="mv")
cli.add_command(cp_cmd, name="cp")
cli.add_command(add_test_cmd, name="add-test")
cli.add_command(newbench_cmd, name="newbench")
cli.add_command(build_cmd, name="build")
cli.add_command(show_cmd, name="show")
cli.add_command(newparam_cmd, name="newparam")
cli.add_command(test_cmd, name="test")
cli.add_command(format_cmd, name="format")
cli.add_command(devcontainer_cmd, name="devcontainer")
cli.add_command(tidy_cmd, name="tidy")
cli.add_command(presets_cmd, name="presets")
cli.add_command(vscode_cmd, name="vscode")
cli.add_command(ci_cmd, name="ci")
cli.add_command(completion_cmd, name="completion")
cli.add_command(precommit_cmd, name="pre-commit")
cli.add_command(docs_cmd, name="docs")
cli.add_command(add_dep_cmd, name="add-dep")
cli.add_command(port_cmd, name="port")
cli.add_command(search_cmd, name="search")
cli.add_command(export_spec_cmd, name="export-spec")
cli.add_command(lint_headers_cmd, name="lint-headers")
cli.add_command(coverage_cmd, name="coverage")
cli.add_command(doctor_cmd, name="doctor")
cli.add_command(sync_cmd, name="sync")
cli.add_command(templates_cmd, name="templates")
cli.add_command(validate_cmd, name="validate")
cli.add_command(version_bump_cmd, name="version-bump")
cli.add_command(publish_cmd, name="publish")
cli.add_command(ls_cmd, name="list")
cli.add_command(ls_cmd, name="ls")


# Load plugin commands
for _extra_cmd in _plugins.load_extra_commands():
    cli.add_command(_extra_cmd)
