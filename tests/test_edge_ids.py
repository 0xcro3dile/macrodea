# Tests for board/edge_ids.py. They run on a PC (Linux): packets are built with
# scapy and handed straight to the detector, alerts are caught before they would
# go to mosquitto_pub.   pytest -q
import importlib.util
import json
import pathlib
import shutil
import sys
import time

import pytest
from scapy.all import ARP, IP, TCP, UDP, Ether

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOARD_IP = "192.168.1.10"
MAC = "02:00:00:00:00:01"

# On a PC the model runs through full TensorFlow, which nags that tf.lite.Interpreter
# is deprecated. The board uses tflite_runtime, so that's not our problem here.
pytestmark = pytest.mark.filterwarnings("ignore:.*tf.lite.Interpreter is deprecated")


def load_detector(monkeypatch, path=ROOT / "board" / "edge_ids.py", **env):
    monkeypatch.setenv("IDS_IFACE", "lo")          # every Linux box has lo
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("edge_ids", path)
    ids = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ids)
    return ids


def capture(monkeypatch, ids):
    alerts = []
    monkeypatch.setattr(ids, "publish", lambda msg: alerts.append(json.loads(msg)))
    return alerts


@pytest.fixture
def detector(monkeypatch):
    ids = load_detector(monkeypatch)
    ids.MODEL = None                               # rules only, the model has its own tests
    return ids, capture(monkeypatch, ids)


def syn(src, dport, sport=40000, mac=MAC):
    return Ether(src=mac) / IP(src=src, dst=BOARD_IP) / TCP(sport=sport, dport=dport, flags="S")


def fin(src, dport, sport=40000, mac=MAC):
    return Ether(src=mac) / IP(src=src, dst=BOARD_IP) / TCP(sport=sport, dport=dport, flags="FA")


def udp(src, dport=80, mac=MAC):
    return Ether(src=mac) / IP(src=src, dst=BOARD_IP) / UDP(sport=5000, dport=dport)


def arp_reply(ip, mac):
    return Ether(src=mac) / ARP(op=2, psrc=ip, hwsrc=mac, pdst=BOARD_IP)


def feed(ids, packets):
    for p in packets:
        ids.on_packet(p)


def types(alerts):
    return [a["type"] for a in alerts]


# --- rules ------------------------------------------------------------------

def test_port_scan_is_reported(detector):
    ids, alerts = detector
    feed(ids, [syn("192.168.1.66", port) for port in range(1, 61)])
    ids.check(time.time(), pps=300)
    assert types(alerts) == ["scan"]
    assert alerts[0]["src"] == "192.168.1.66"
    assert alerts[0]["detector"] == "rule"


def test_quiet_client_is_not_reported(detector):
    ids, alerts = detector
    for i in range(5):
        feed(ids, [syn("192.168.1.20", 1883, sport=41000 + i), fin("192.168.1.20", 1883, sport=41000 + i)])
    ids.check(time.time(), pps=10)
    assert alerts == []


def test_brute_force_on_one_port(detector):
    ids, alerts = detector
    feed(ids, [syn("192.168.1.66", 22, sport=42000 + i) for i in range(30)])
    ids.check(time.time(), pps=50)
    assert types(alerts) == ["bruteforce"]


def test_slowloris_holds_connections_open(detector):
    ids, alerts = detector
    feed(ids, [syn("192.168.1.66", 1883, sport=43000 + i) for i in range(40)])
    ids.check(time.time(), pps=50)
    assert types(alerts) == ["slowloris"]


def test_connections_closed_with_fin_do_not_count_as_held(detector):
    ids, alerts = detector
    for i in range(40):
        feed(ids, [syn("192.168.1.66", 1883, sport=43000 + i), fin("192.168.1.66", 1883, sport=43000 + i)])
    ids.check(time.time(), pps=50)
    assert "slowloris" not in types(alerts)


def test_flood_blames_the_loudest_source(detector):
    ids, alerts = detector
    feed(ids, [udp("192.168.1.66") for _ in range(50)] + [udp("192.168.1.20") for _ in range(5)])
    ids.check(time.time(), pps=50_000)
    assert types(alerts) == ["flood"]
    assert alerts[0]["src"] == "192.168.1.66"


def test_arp_reply_with_a_new_mac_is_reported_as_mitm(detector):
    ids, alerts = detector
    feed(ids, [arp_reply("192.168.1.1", "02:00:00:00:00:aa"), arp_reply("192.168.1.1", "02:00:00:00:00:bb")])
    assert types(alerts) == ["mitm"]
    assert alerts[0]["src"] == "192.168.1.1"


def test_internet_sources_are_ignored(detector):
    ids, alerts = detector
    feed(ids, [syn("8.8.8.8", port) for port in range(1, 61)])
    ids.check(time.time(), pps=300)
    assert alerts == []


def test_old_packets_fall_out_of_the_window(detector):
    ids, alerts = detector
    feed(ids, [syn("192.168.1.66", port) for port in range(1, 61)])
    ids.check(time.time() + ids.WINDOW + 1, pps=10)
    assert alerts == []


def test_same_alert_is_not_repeated_within_the_cooldown(detector):
    ids, alerts = detector
    feed(ids, [syn("192.168.1.66", port) for port in range(1, 61)])
    ids.check(time.time(), pps=300)
    ids.check(time.time(), pps=300)
    assert types(alerts) == ["scan"]


def test_env_lists_can_have_spaces_after_commas(monkeypatch):
    ids = load_detector(monkeypatch, IDS_LAN="192.168.1., 10.0.0.",
                        IDS_NAMES="192.168.1.66=plc, 10.0.0.5=hmi")
    ids.MODEL = None
    alerts = capture(monkeypatch, ids)
    feed(ids, [syn("10.0.0.5", port) for port in range(1, 61)])
    ids.check(time.time(), pps=300)
    assert types(alerts) == ["scan"]
    assert alerts[0]["who"] == "hmi"


def test_record_mode_writes_labelled_rows_next_to_the_script(monkeypatch, tmp_path):
    shutil.copy(ROOT / "board" / "edge_ids.py", tmp_path)
    monkeypatch.setattr(sys, "argv", ["edge_ids.py", "--record", "scan"])
    ids = load_detector(monkeypatch, path=tmp_path / "edge_ids.py")
    capture(monkeypatch, ids)
    feed(ids, [syn("192.168.1.66", port) for port in range(1, 61)])
    ids.check(time.time(), pps=300)
    ids.rec.close()
    lines = (tmp_path / "dataset.csv").read_text().splitlines()
    assert lines[0] == "ts,src,pkts,ports,syns,top_port,held,nic_pps,label"
    assert lines[1].split(",")[1:] == ["192.168.1.66", "60", "60", "60", "1", "1", "300", "scan"]


def test_watcher_sends_a_heartbeat_every_5_seconds(detector, monkeypatch):
    # The dashboard only trusts "all clear" while these keep coming, so they
    # have to come from the detection loop itself, not just a live process.
    ids, _ = detector
    status = []
    monkeypatch.setattr(ids, "publish", lambda msg, topic="ids/alerts":
                        status.append(json.loads(msg)) if topic == "ids/status" else None)
    ticks = []

    def fake_sleep(s):
        if len(ticks) == 12:
            raise KeyboardInterrupt            # stop the endless loop after 12 ticks
        ticks.append(s)

    monkeypatch.setattr(ids, "time", type("T", (), {"sleep": staticmethod(fake_sleep),
                                                    "time": staticmethod(time.time),
                                                    "strftime": staticmethod(time.strftime)}))
    monkeypatch.setattr(ids, "rx_packets", lambda: 0)
    with pytest.raises(KeyboardInterrupt):
        ids.watcher()
    assert len(status) == 2
    assert status[0]["model"] == "off"


# --- the int8 model (needs tflite_runtime or tensorflow) ---------------------

@pytest.fixture
def with_model(monkeypatch):
    pytest.importorskip("tensorflow")
    ids = load_detector(monkeypatch)
    assert ids.MODEL is not None, "model.tflite should load through tensorflow when tflite_runtime is missing"
    return ids, capture(monkeypatch, ids)


# typical windows (median of each class) from data/dataset.csv:
#   pkts, ports, syns, top_port, held, nic_pps
@pytest.mark.parametrize("label, feats", [
    ("normal",     [30, 3, 4, 4, 0, 5]),
    ("scan",       [89, 50, 71, 2, 2, 10]),
    ("flood",      [63, 2, 0, 0, 0, 87267]),
    ("bruteforce", [125, 2, 38, 38, 2, 11]),
    ("slowloris",  [12, 2, 0, 0, 25, 0]),
])
def test_model_recognises_recorded_traffic(with_model, label, feats):
    ids, _ = with_model
    got, confidence = ids.model_predict(feats)
    assert got == label
    assert confidence >= 0.75


def test_model_makes_the_call_on_live_traffic(with_model):
    ids, alerts = with_model
    feed(ids, [syn("192.168.1.66", port) for port in range(1, 61)])
    ids.check(time.time(), pps=300)
    assert types(alerts) == ["scan"]
    assert alerts[0]["detector"] == "model"
