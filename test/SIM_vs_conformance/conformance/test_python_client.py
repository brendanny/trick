"""The Python client, share/trick/pymods/trick/variable_server.py, against the server.

The client is part of the variable server's public API (TrickOps and user
scripts use it), so the suite checks that its methods work end to end. The
SIM is a separate instance because the tests write values.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

import pytest
from conftest import HOST, start_sim

P = "conf.vars."
CLIENT_PATH = Path(__file__).resolve().parents[3] / "share" / "trick" / "pymods" / "trick" / "variable_server.py"


def _load_client():
    spec = importlib.util.spec_from_file_location("trick_variable_server_under_test", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module  # dataclasses look the module up
    spec.loader.exec_module(module)
    return module


vs_client = _load_client()


@pytest.fixture(scope="module")
def client_sim(pytestconfig: pytest.Config):
    sim = start_sim(pytestconfig, "python_client")
    yield sim
    sim.stop()


@pytest.fixture
def vs(client_sim):
    with vs_client.VariableServer(HOST, client_sim.port) as server:
        yield server


def test_get_value(vs) -> None:
    assert vs.get_value(P + "i32") == "-123456789"
    assert vs.get_value(P + "i32", type_=int) == -123456789
    assert vs.get_value(P + "pos", units="km", type_=float) == pytest.approx(1.0)


def test_get_value_bad_units(vs) -> None:
    with pytest.raises(vs_client.UnitsConversionError):
        vs.get_value(P + "pos", units="kg")


def test_get_values_updates_the_variables(vs) -> None:
    i32 = vs_client.Variable(P + "i32", type_=int)
    pos = vs_client.Variable(P + "pos", units="cm", type_=float)
    assert vs.get_values(i32, pos) == [-123456789, pytest.approx(100000.0)]
    assert i32.units is None or i32.units == "--"
    assert repr(pos) == f"{P}pos = 100000.0 cm"
    assert str(pos) == P + "pos"
    assert vs.get_values() == []


def test_set_value(vs) -> None:
    vs.set_value(P + "unitless", 7.25)
    assert vs.get_value(P + "unitless", type_=float) == 7.25
    vs.set_value(P + "str", "set by the client")
    assert vs.get_value(P + "str") == "set by the client"
    vs.set_value(P + "pos", 2.0, units="km")
    assert vs.get_value(P + "pos", type_=float) == 2000.0
    vs.set_value(P + "pos", 1000.0)


def test_variable_exists_and_stl_size(vs) -> None:
    assert vs.variable_exists(P + "i32")
    assert not vs.variable_exists(P + "no_such_variable")
    assert vs.get_stl_size(P + "vec") == 3
    assert vs.get_stl_size(P + "vec_empty") == 0


def test_sampling_and_callbacks(vs) -> None:
    i32 = vs_client.Variable(P + "i32", type_=int)
    d = vs_client.Variable(P + "d", type_=float)
    updated = threading.Event()
    vs.register_callback(updated.set)
    vs.set_period(0.05)
    vs.add_variables(i32, d)
    vs.add_variables(i32)  # already sampled: no effect
    vs.pause(False)
    assert updated.wait(10.0)
    assert i32.value == -123456789
    assert d.value == pytest.approx(3.141592653589793)
    vs.remove_variables(d)
    vs.remove_all_variables()
    vs.deregister_callback(updated.set)


def test_settings_commands_are_accepted(vs) -> None:
    vs.set_tag("python_client")
    vs.set_debug(0)
    for mode in vs.CopyMode:
        vs.set_copy_mode(mode)
    vs.set_copy_mode(vs.CopyMode.ASYNC)
    vs.send_on_copy(False)
    vs.validate_addresses(True)
    vs.set_units(P + "pos", "m")
    # The commands leave no reply on the synchronous channel.
    assert vs.get_value(P + "i32", type_=int) == -123456789


def test_enums_keep_the_old_values() -> None:
    channel = vs_client.VariableServer.Channel
    assert (channel.ASYNC, channel.SYNC, channel.BOTH) == ("ASYNC", "SYNC", "BOTH")
    assert f"x_{channel.SYNC}" == "x_SYNC"
    copy_mode = vs_client.VariableServer.CopyMode
    assert (copy_mode.ASYNC, copy_mode.SCHEDULED, copy_mode.TOP_OF_FRAME) == (0, 1, 2)
    indicator = vs_client.Message.Indicator
    assert (indicator.VAR_SEND, indicator.VAR_EXISTS, indicator.VAR_GET_STL_SIZE) == (0, 1, 6)
    message = vs_client.Message(0, "x")
    assert message == (0, "x") and message.indicator == 0 and message.data == "x"


def test_variables_compare_by_identity() -> None:
    a = vs_client.Variable(P + "i32")
    b = vs_client.Variable(P + "i32")
    assert a != b and a == a
    assert len({a, b}) == 2


def test_close_is_safe_to_repeat(client_sim) -> None:
    server = vs_client.VariableServer(HOST, client_sim.port)
    assert str(server).startswith("VariableServer(")
    server.close()
    server.close()
