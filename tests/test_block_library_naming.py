"""Tests for generated GNU Radio block-library target names."""

from gr4_modtool.commands.newmod import block_library_name


def test_block_library_name_uses_gr_convention() -> None:
    assert block_library_name("plugin_sample", "basic") == "GrPluginSampleBasicBlocks"


def test_block_library_name_handles_flat_projects() -> None:
    assert block_library_name("plugin-sample") == "GrPluginSampleBlocks"
