"""E2E: port command workflow.

Tests importing a GNURadio 3.x Python block and scaffolding a gr4 header.
"""

from __future__ import annotations

from pathlib import Path

from gr4_modtool.project.discovery import ProjectConfig

from .conftest import invoke

_SYNC_BLOCK_SRC = """\
import numpy as np
import gnuradio.gr as gr

class low_pass_filter(gr.sync_block):
    \"\"\"A simple low-pass filter.\"\"\"
    def __init__(self, cutoff=1000.0, gain=1.0):
        gr.sync_block.__init__(
            self,
            name="low_pass_filter",
            in_sig=[np.float32],
            out_sig=[np.float32],
        )
        self.cutoff = cutoff
        self.gain = gain

    def work(self, input_items, output_items):
        output_items[0][:] = input_items[0]
        return len(output_items[0])
"""

_DECIM_BLOCK_SRC = """\
import numpy as np
import gnuradio.gr as gr

class my_decimator(gr.decim_block):
    \"\"\"A decimating block.\"\"\"
    def __init__(self, decimation=4):
        gr.decim_block.__init__(
            self,
            name="my_decimator",
            in_sig=[np.float32],
            out_sig=[np.float32],
            decim=decimation,
        )

    def work(self, input_items, output_items):
        return len(output_items[0])
"""

_INTERP_BLOCK_SRC = """\
import numpy as np
import gnuradio.gr as gr

class my_interpolator(gr.interp_block):
    \"\"\"An interpolating block.\"\"\"
    def __init__(self, interp=2):
        gr.interp_block.__init__(
            self,
            name="my_interpolator",
            in_sig=[np.float32],
            out_sig=[np.float32],
            interp=interp,
        )

    def work(self, input_items, output_items):
        return len(output_items[0])
"""

_BASIC_BLOCK_SRC = """\
import numpy as np
import gnuradio.gr as gr

class my_source(gr.basic_block):
    \"\"\"A basic source block with no archetype.\"\"\"
    def __init__(self):
        gr.basic_block.__init__(
            self,
            name="my_source",
            in_sig=[],
            out_sig=[np.float32],
        )

    def work(self, input_items, output_items):
        return len(output_items[0])
"""

_COMPLEX_BLOCK_SRC = """\
import numpy as np
import gnuradio.gr as gr

class complex_filter(gr.sync_block):
    \"\"\"A complex-valued filter.\"\"\"
    def __init__(self, center_freq=0.0):
        gr.sync_block.__init__(
            self,
            name="complex_filter",
            in_sig=[np.complex64],
            out_sig=[np.complex64],
        )
        self.center_freq = center_freq

    def work(self, input_items, output_items):
        output_items[0][:] = input_items[0]
        return len(output_items[0])
"""

_INT_BLOCK_SRC = """\
import numpy as np
import gnuradio.gr as gr

class int_processor(gr.sync_block):
    \"\"\"An integer-processing block.\"\"\"
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="int_processor",
            in_sig=[np.int32],
            out_sig=[np.int32],
        )

    def work(self, input_items, output_items):
        return len(output_items[0])
"""

_NO_PARAMS_SRC = """\
import numpy as np
import gnuradio.gr as gr

class pass_through(gr.sync_block):
    \"\"\"A pass-through block with no parameters.\"\"\"
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="pass_through",
            in_sig=[np.float32],
            out_sig=[np.float32],
        )

    def work(self, input_items, output_items):
        output_items[0][:] = input_items[0]
        return len(output_items[0])
"""

_DOCSTRING_SRC = """\
import numpy as np
import gnuradio.gr as gr

class documented_block(gr.sync_block):
    \"\"\"Unique docstring for testing description injection.\"\"\"
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="documented_block",
            in_sig=[np.float32],
            out_sig=[np.float32],
        )

    def work(self, input_items, output_items):
        return len(output_items[0])
"""

_NO_GR3_SRC = """\
class RegularPythonClass:
    def __init__(self):
        pass
"""


# ---------------------------------------------------------------------------
# Successful ports
# ---------------------------------------------------------------------------


def test_port_creates_header(project: ProjectConfig, tmp_path: Path) -> None:
    """port creates a gr4 header from a gr3 sync_block source."""
    src = tmp_path / "low_pass_filter.py"
    src.write_text(_SYNC_BLOCK_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    header = project.group_include_dir("basic") / "LowPassFilter.hpp"
    assert header.exists()


def test_port_creates_test_file(project: ProjectConfig, tmp_path: Path) -> None:
    """port generates a qa_*.cpp test alongside the header."""
    src = tmp_path / "low_pass_filter.py"
    src.write_text(_SYNC_BLOCK_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    qa = project.group_test_dir("basic") / "qa_LowPassFilter.cpp"
    assert qa.exists()


def test_port_injects_params(project: ProjectConfig, tmp_path: Path) -> None:
    """port injects Annotated<> parameters from gr3 __init__ arguments."""
    src = tmp_path / "low_pass_filter.py"
    src.write_text(_SYNC_BLOCK_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    header = (project.group_include_dir("basic") / "LowPassFilter.hpp").read_text()
    assert "cutoff" in header
    assert "gain" in header


def test_port_decim_block(project: ProjectConfig, tmp_path: Path) -> None:
    """port handles gr3 decim_block base class."""
    src = tmp_path / "my_decimator.py"
    src.write_text(_DECIM_BLOCK_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    header = project.group_include_dir("basic") / "MyDecimator.hpp"
    assert header.exists()


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_port_errors_on_non_gr3_source(project: ProjectConfig, tmp_path: Path) -> None:
    """port exits nonzero when the source file has no gr3 block class."""
    src = tmp_path / "not_a_block.py"
    src.write_text(_NO_GR3_SRC)

    result = invoke(project.root, "port", str(src), "--group", "basic", "-y", expect_ok=False)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Additional base-class coverage
# ---------------------------------------------------------------------------


def test_port_interp_block_creates_header(project: ProjectConfig, tmp_path: Path) -> None:
    """port handles gr3 interp_block and maps it to the interpolator archetype."""
    src = tmp_path / "my_interpolator.py"
    src.write_text(_INTERP_BLOCK_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    assert (project.group_include_dir("basic") / "MyInterpolator.hpp").exists()


def test_port_basic_block_creates_header(project: ProjectConfig, tmp_path: Path) -> None:
    """port handles gr3 basic_block (no archetype fallback) and still creates a header."""
    src = tmp_path / "my_source.py"
    src.write_text(_BASIC_BLOCK_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    assert (project.group_include_dir("basic") / "MySource.hpp").exists()


# ---------------------------------------------------------------------------
# Numpy type-mapping coverage
# ---------------------------------------------------------------------------


def test_port_complex_type_in_header(project: ProjectConfig, tmp_path: Path) -> None:
    """port maps np.complex64 → std::complex<float> in the generated header."""
    src = tmp_path / "complex_filter.py"
    src.write_text(_COMPLEX_BLOCK_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    header = (project.group_include_dir("basic") / "ComplexFilter.hpp").read_text()
    assert "std::complex" in header


def test_port_int_type_in_header(project: ProjectConfig, tmp_path: Path) -> None:
    """port maps np.int32 → int32_t in the generated header."""
    src = tmp_path / "int_processor.py"
    src.write_text(_INT_BLOCK_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    header = (project.group_include_dir("basic") / "IntProcessor.hpp").read_text()
    assert "int32_t" in header


# ---------------------------------------------------------------------------
# Parameter and description coverage
# ---------------------------------------------------------------------------


def test_port_no_params_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """port succeeds and check passes for a block with no __init__ parameters."""
    import json

    src = tmp_path / "pass_through.py"
    src.write_text(_NO_PARAMS_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    assert (project.group_include_dir("basic") / "PassThrough.hpp").exists()
    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_port_sync_block_check_clean(project: ProjectConfig, tmp_path: Path) -> None:
    """check passes after porting a sync_block (validates full registration)."""
    import json

    src = tmp_path / "low_pass_filter.py"
    src.write_text(_SYNC_BLOCK_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    result = invoke(project.root, "check", "--json")
    assert json.loads(result.output)["error_count"] == 0


def test_port_docstring_used_as_description(project: ProjectConfig, tmp_path: Path) -> None:
    """port uses the gr3 class docstring as the block description in the header."""
    src = tmp_path / "documented_block.py"
    src.write_text(_DOCSTRING_SRC)

    invoke(project.root, "port", str(src), "--group", "basic", "-y")

    header = (project.group_include_dir("basic") / "DocumentedBlock.hpp").read_text()
    assert "Unique docstring for testing description injection" in header
