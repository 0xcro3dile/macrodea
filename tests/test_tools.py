# The helper scripts talk to a board over the network, so without a board
# address they must stop with a usage line instead of guessing one.
# ssh, ping etc. are replaced by stubs that log the call, so nothing leaves this machine.
import os
import pathlib
import subprocess
import sys
import tarfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def fake_bin(tmp_path):
    log = tmp_path / "calls.log"
    for name in ["ssh", "scp", "tar", "ping", "python3", "sg", "wireshark"]:
        stub = tmp_path / name
        stub.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\nexit 1\n')
        stub.chmod(0o755)
    return tmp_path, log


@pytest.mark.parametrize("cmd", [
    ["sh", "deploy.sh"],
    ["sh", "tools/measure.sh"],
    ["sh", "tools/watch-traffic.sh"],
    [sys.executable, "tools/dashboard.py"],
    [sys.executable, "tools/arp_selftest.py"],
    [sys.executable, "tools/simulate.py"],
])
def test_refuses_to_run_without_a_board_address(fake_bin, cmd):
    bindir, log = fake_bin
    env = dict(os.environ, PATH=f"{bindir}:/usr/bin:/bin", BOARD="")
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
    assert r.returncode != 0
    assert "usage" in (r.stdout + r.stderr).lower()
    assert not log.exists(), "touched the network before checking its arguments:\n" + log.read_text()


def test_deploy_ships_everything_the_board_needs(tmp_path):
    # fake ssh: keep whatever deploy.sh pipes into it (the tar stream)
    payload = tmp_path / "payload.tar"
    ssh = tmp_path / "ssh"
    ssh.write_text(f'#!/bin/sh\ncat > "{payload}"\n')
    ssh.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:/usr/bin:/bin")
    r = subprocess.run(["sh", "deploy.sh", "192.0.2.1"], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    with tarfile.open(payload) as tar:
        shipped = set(tar.getnames())
    assert shipped == {"edge_ids.py", "model.tflite", "model.json", "edge-ids.service",
                       "metrics.py", "sample_traffic.py"}
