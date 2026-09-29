# tools/dashboard.py must only look "all clear" while it is really hearing from
# the board. A fake ssh on PATH plays the board.
import importlib.util
import json
import pathlib
import socketserver
import threading
import time
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def dashboard():
    spec = importlib.util.spec_from_file_location("dashboard", ROOT / "tools" / "dashboard.py")
    dash = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dash)
    dash.BOARD = "192.0.2.1"
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), dash.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    dash.url = f"http://127.0.0.1:{server.server_address[1]}"
    yield dash
    server.shutdown()
    server.server_close()


def fake_ssh(tmp_path, monkeypatch, script):
    ssh = tmp_path / "ssh"
    ssh.write_text("#!/bin/sh\n" + script)
    ssh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")


def state(dash):
    with urllib.request.urlopen(dash.url + "/state", timeout=5) as r:
        return json.load(r)


def wait_for(cond, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def test_no_link_before_the_board_answers(dashboard):
    s = state(dashboard)
    assert s["link"] is False
    assert s["detector"] is False
    assert s["alerts"] == []


def test_board_alerts_come_through_once_the_link_is_up(dashboard, tmp_path, monkeypatch):
    # mosquitto_sub -v prints "topic payload"
    alert = {"time": "12:00:00", "type": "scan", "src": "192.168.1.66", "who": "unknown",
             "detector": "model", "detail": "model 99% (ports=60 held=1)"}
    fake_ssh(tmp_path, monkeypatch, "echo link-up\n"
             f"echo 'ids/status {{\"ts\": 1, \"model\": \"on\"}}'\n"
             f"echo 'ids/alerts {json.dumps(alert)}'\nsleep 30\n")
    threading.Thread(target=dashboard.alert_reader, daemon=True).start()
    assert wait_for(lambda: state(dashboard)["detector"] and state(dashboard)["alerts"])
    got = state(dashboard)["alerts"][0]
    assert (got["type"], got["src"], got["detector"]) == ("scan", "192.168.1.66", "model")


def test_not_all_clear_while_the_detector_is_silent(dashboard, tmp_path, monkeypatch):
    # ssh and the broker answer, but edge-ids itself sends no heartbeat
    # (service stopped or crash-looping)
    fake_ssh(tmp_path, monkeypatch, "echo link-up\nsleep 30\n")
    threading.Thread(target=dashboard.alert_reader, daemon=True).start()
    assert wait_for(lambda: state(dashboard)["link"])
    assert state(dashboard)["detector"] is False


def test_link_goes_down_when_the_board_connection_dies(dashboard, tmp_path, monkeypatch):
    # first connection works for a moment, every retry after that fails
    flag = tmp_path / "connected-once"
    fake_ssh(tmp_path, monkeypatch,
             f'if [ ! -e "{flag}" ]; then touch "{flag}"; echo link-up; sleep 1; fi\nexit 255\n')
    threading.Thread(target=dashboard.alert_reader, daemon=True).start()
    assert wait_for(lambda: state(dashboard)["link"])
    assert wait_for(lambda: not state(dashboard)["link"])
