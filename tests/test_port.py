"""Tests for the gr3 port command."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.commands.newgroup import write_group_skeleton
from gr4_modtool.commands.port import parse_gr3_python, port_gr3_block
from gr4_modtool.project.discovery import ProjectConfig, save_config

_SYNC_BLOCK = '''\
import numpy as np
from gnuradio import gr

class my_filter(gr.sync_block):
    """A simple gain filter."""
    def __init__(self, gain=1.0):
        gr.sync_block.__init__(self,
            name='my_filter',
            in_sig=[np.float32],
            out_sig=[np.float32])
        self.gain = gain

    def work(self, input_items, output_items):
        output_items[0][:] = input_items[0] * self.gain
        return len(output_items[0])
'''

_DECIM_BLOCK = '''\
import numpy as np
from gnuradio import gr

class my_decimator(gr.decim_block):
    """A decimating block."""
    def __init__(self, decim=4):
        gr.decim_block.__init__(self,
            name='my_decimator',
            in_sig=[np.complex64],
            out_sig=[np.complex64],
            decim=decim)
        self.decim = decim

    def work(self, input_items, output_items):
        return len(output_items[0])
'''

_COMPLEX_BLOCK = """\
import numpy as np
from gnuradio import gr

class ComplexFilter(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self,
            name='ComplexFilter',
            in_sig=[np.complex128],
            out_sig=[np.float64])
"""


@pytest.fixture()
def cfg(tmp_path: Path) -> ProjectConfig:
    c = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(c)
    (tmp_path / "blocks").mkdir()
    write_group_skeleton(c, "basic")
    return c


def test_port_parses_block_name() -> None:
    info = parse_gr3_python(_SYNC_BLOCK)
    assert info["block_name"] == "MyFilter"


def test_port_parses_in_sigs() -> None:
    info = parse_gr3_python(_SYNC_BLOCK)
    assert "np.float32" in info["in_sigs"]


def test_port_maps_sync_to_filter() -> None:
    info = parse_gr3_python(_SYNC_BLOCK)
    assert info["gr3_base"] == "sync_block"


def test_port_maps_decim_to_decimator() -> None:
    info = parse_gr3_python(_DECIM_BLOCK)
    assert info["gr3_base"] == "decim_block"


def test_port_creates_header(tmp_path: Path, cfg: ProjectConfig) -> None:
    src = tmp_path / "my_filter.py"
    src.write_text(_SYNC_BLOCK)
    written = port_gr3_block(cfg, "basic", src)
    header = cfg.group_include_dir("basic") / "MyFilter.hpp"
    assert header.exists()
    assert any(p == header for p in written)


def test_port_maps_numpy_float32_to_type_list(tmp_path: Path, cfg: ProjectConfig) -> None:
    src = tmp_path / "my_filter.py"
    src.write_text(_SYNC_BLOCK)
    port_gr3_block(cfg, "basic", src)
    text = (cfg.group_include_dir("basic") / "MyFilter.hpp").read_text()
    assert "float" in text


def test_port_maps_numpy_complex64(tmp_path: Path, cfg: ProjectConfig) -> None:
    src = tmp_path / "my_dec.py"
    src.write_text(_DECIM_BLOCK)
    port_gr3_block(cfg, "basic", src)
    text = (cfg.group_include_dir("basic") / "MyDecimator.hpp").read_text()
    assert "complex" in text.lower() or "MyDecimator" in text


def test_port_raises_on_non_gr3_file() -> None:
    with pytest.raises(ValueError, match="No GNURadio 3 block"):
        parse_gr3_python("class Foo: pass")
