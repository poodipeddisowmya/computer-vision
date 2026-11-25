"""camcal - production camera calibration for the OS08A10 8MP USB camera on Jetson.

    python3 -m camcal devices                       list V4L2 devices
    python3 -m camcal probe                         dump every mode + control of the camera
    python3 -m camcal board --preset charuco_a3     print-ready PDF (already in boards/)
    python3 -m camcal measure --span-x 350.10 --span-y 249.85   enter caliper measurements
    python3 -m camcal export                        write os08a10_camera_config.yaml (everything in one file)
    python3 -m camcal still                         MOST ACCURATE: rest the camera for each shot (8-frame average)
    python3 -m camcal simple                        EASIEST: move the camera, images are taken, ENTER -> calibration
    python3 -m camcal preview                       live view with overlays; click START -> auto
    python3 -m camcal auto                          EVERYTHING: all resolutions, guided auto-capture, calibrate
    python3 -m camcal capture --profile 4k_mjpg     one resolution (automatic capture) -> calibrate
    python3 -m camcal calibrate sessions/<dir>      (re)calibrate a session
    python3 -m camcal verify --profile 4k_mjpg      live metric accuracy check
    python3 -m camcal summary                       all calibrated modes side by side
    python3 -m camcal selftest                      ground-truth synthetic test
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("camcal")


def load_cfg(path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def resolve_device(cfg: dict, override: str | None) -> str:
    from .v4l2 import find_device, list_devices
    if override:
        return override
    c = cfg.get("camera", {})
    if c.get("device") and c["device"] != "auto":
        return c["device"]
    dev = find_device(c.get("match_card") or None, c.get("usb_serial"), c.get("usb_port_path"))
    if not dev:
        raise SystemExit(f"no matching camera. Devices: {json.dumps(list_devices(), indent=1)}")
    return dev


def default_board() -> Path:
    for name in ("charuco_a3", "charuco_a4"):
        p = ROOT / "boards" / f"{name}.json"
        if p.exists():
            return p
    raise SystemExit("no board json in boards/")


# ----------------------------------------------------------------------------- commands
def cmd_devices(a, cfg):
    from .v4l2 import list_devices
    for d in list_devices():
        print(json.dumps(d))


def cmd_probe(a, cfg):
    from .v4l2 import V4L2Device, control_dump
    dev = resolve_device(cfg, a.device)
    with V4L2Device(dev) as d:
        info, fmts, ctrls = d.info(), d.formats(), d.controls()
        print(json.dumps(info, indent=1))
        print("\nMODES:")
        for f in fmts:
            for s in f["sizes"]:
                if "width" in s:
                    print(f"  {f['fourcc']:5s} {s['width']:5d}x{s['height']:<5d} fps {s['fps']}")
        print("\nCONTROLS:")
        print(d.describe_controls())
    out = ROOT / "camera_probe.json"
    out.write_text(json.dumps({"time": dt.datetime.now().isoformat(), "device": info, "formats": fmts,
                               "controls": control_dump(ctrls)}, indent=1))
    print(f"\nsaved {out}")


def cmd_board(a, cfg):
    from .board import PRESETS, BoardSpec
    from .board_pdf import make_board_pdf, verify_pdf_detects
    spec = PRESETS[a.preset]
    paper = a.paper or ("A3" if a.preset.endswith("a3") else "A4")
    pdf = ROOT / "boards" / f"{a.preset}.pdf"
    make_board_pdf(spec, paper, pdf, ROOT / "boards" / f"{a.preset}_preview.png")
    jp = ROOT / "boards" / f"{a.preset}.json"
    if jp.exists() and BoardSpec.load(jp).is_measured:
        print(f"keeping measured {jp} (delete it to reset the measurement)")
    else:
        spec.save(jp)
    n, tot = verify_pdf_detects(spec, pdf)
    print(f"{pdf}  ({paper}) - self-check: {n}/{tot} corners detected from the rasterised PDF")


def cmd_measure(a, cfg):
    from .board import BoardSpec
    p = Path(a.board) if a.board else default_board()
    spec = BoardSpec.load(p)
    spec.measured_span_x_mm, spec.measured_span_y_mm = a.span_x, a.span_y
    nx, ny = spec.squares_x * spec.square_mm, spec.squares_y * spec.square_mm
    spec.save(p)
    sx, sy = 100 * (a.span_x / nx - 1), 100 * (a.span_y / ny - 1)
    print(f"{p}: pitch X {spec.pitch_x_mm:.4f} mm ({sx:+.3f}%), Y {spec.pitch_y_mm:.4f} mm ({sy:+.3f}%)")
    if abs(sx) > 1 or abs(sy) > 1:
        print("WARNING: >1% off nominal - was the PDF printed with 'fit to page'? Reprint at 100%.")
    if abs(sx - sy) > 0.15:
        print(f"note: X/Y print scale differ by {abs(sx - sy):.3f}% - this is exactly why measuring matters.")


def _slow_mode_tweaks(cc, mode):
    """1 fps (YUYV 4K) modes: fewer frames per capture, more patience per target."""
    if mode.fps <= 2:
        cc.frames_to_average = min(cc.frames_to_average, 2)
        cc.target_timeout_s *= 3
        cc.stable_time_s = max(cc.stable_time_s, 1.5)


def _capture_cfg(cfg, a):
    from .capture import CaptureConfig
    cc = CaptureConfig(**{k: v for k, v in (cfg.get("capture") or {}).items() if k in CaptureConfig.__dataclass_fields__})
    if getattr(a, "warmup_min", None) is not None:
        cc.warmup_minutes = a.warmup_min
    if getattr(a, "views", None):
        cc.target_views = a.views
    return cc


def cmd_capture(a, cfg):
    from .board import BoardSpec
    from .camera import Mode
    from .capture import run_capture_session
    mode = Mode.from_dict(cfg["profiles"][a.profile])
    spec = BoardSpec.load(a.board or default_board())
    cc = _capture_cfg(cfg, a)
    _slow_mode_tweaks(cc, mode)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "sessions" / f"{mode.key}_{stamp}"
    lock = dict(cfg.get("calibration_lock") or {})
    for kv in a.set or []:
        k, v = kv.split("=")
        lock[k] = int(v)
    device = None if a.simulate else resolve_device(cfg, a.device)
    log.info("capture %s on %s -> %s", mode.key, device or a.simulate, out)
    log.info("board: %s", spec.describe())
    run_capture_session(device, mode, spec, out, cc, lock, simulate=a.simulate, auto=not a.manual)
    print(f"session saved: {out}")
    if not a.no_calibrate:
        a.session = str(out)
        cmd_calibrate(a, cfg)


def run_calibration(sess: Path, cfg: dict, board: str | None = None, out: str | None = None,
                    model: str | None = None, fast: bool = False) -> dict:
    from .board import BoardSpec
    from .calibrate import calibrate_session
    spec = BoardSpec.load(Path(board) if board else (sess / "board.json"))
    master = ROOT / "boards" / f"{spec.name}.json"
    if not spec.is_measured and master.exists() and BoardSpec.load(master).is_measured:
        spec = BoardSpec.load(master)
        log.info("using measured board definition %s", master)
    meta = json.loads((sess / "session.json").read_text()) if (sess / "session.json").exists() else {}
    key = f"{meta['mode']['width']}x{meta['mode']['height']}_{meta['mode']['fourcc']}" if meta.get("mode") else sess.name
    outp = Path(out) if out else ROOT / "calibrations" / key
    c = cfg.get("calibration", {})
    r = calibrate_session(sess, spec, outp, model=model or c.get("model", "auto"),
                          candidates=c.get("candidates"), min_corners=c.get("min_corners", 15),
                          folds=c.get("folds", 5), n_boot=0 if fast else c.get("bootstrap", 30),
                          working_distances_mm=c.get("working_distances_mm", (250, 500, 1000)))
    r["_out_dir"] = str(outp)
    return r


def cmd_calibrate(a, cfg):
    r = run_calibration(Path(a.session), cfg, board=getattr(a, "board", None), out=getattr(a, "out", None),
                        model=getattr(a, "model", None), fast=getattr(a, "fast", False))
    print((Path(r["_out_dir"]) / f"camera_{r['mode_key']}_summary.md").read_text())
    print(f"outputs in {r['_out_dir']}")


def summary_text(root: Path) -> str:
    from .runtime import CalibrationStore
    st = CalibrationStore(root)
    rows = []
    for k in st.modes():
        wh, fcc = k.split("_")[0], k.split("_")[1]
        c = st.for_mode(*map(int, wh.split("x")), fcc)
        rows.append((k, c, c.data))
    if not rows:
        return "no calibrations yet"
    ref = max(rows, key=lambda r: r[1].size[0])
    out = [f"{'mode':16s} {'grade':5s} {'model':13s} {'rms px':>7s} {'fx':>9s} {'fy':>9s} {'cx':>8s} {'cy':>8s} "
           f"{'HFOV':>6s} {'unc px':>6s} {'holdout mm (p95)':>16s}  relation to {ref[0]}"]
    for k, c, d in rows:
        sx = c.size[0] / ref[1].size[0]
        f_ratio = c.K[0, 0] / ref[1].K[0, 0]
        rel = "reference" if k == ref[0] else ("scaled, same FOV" if abs(f_ratio / sx - 1) < 0.01 else
                                               f"different FOV (crop?) f-ratio {f_ratio:.3f} vs size {sx:.3f}")
        hm = d.get("holdout_metric") or {}
        hm_s = f"{hm.get('holdout_mm_p95', float('nan')):.3f}@{hm.get('holdout_distance_mm_median', 0):.0f}mm" if hm else "-"
        out.append(f"{k:16s} {d['grade']:5s} {d['distortion_model']:13s} {d['rms_px']:7.4f} {c.K[0, 0]:9.2f} "
                   f"{c.K[1, 1]:9.2f} {c.K[0, 2]:8.2f} {c.K[1, 2]:8.2f} {d['fov_deg']['horizontal']:6.2f} "
                   f"{d.get('bootstrap', {}).get('uncertainty_px_max', float('nan')):6.3f} {hm_s:>16s}  {rel}")
    return "\n".join(out)


def preflight(device: str, profiles: dict) -> dict:
    """Open each mode briefly; return {name: None | error}."""
    from .camera import Camera, Mode
    res = {}
    for name, p in profiles.items():
        m = Mode.from_dict(p)
        try:
            cam = Camera(device, m)
            cam.wait_frames(1, timeout=max(8.0, 4.0 / max(m.fps, 0.1)))
            cam.release()
            res[name] = None
            log.info("preflight %-12s %s OK", name, m.key)
        except Exception as e:
            res[name] = str(e)
            log.warning("preflight %-12s %s NOT AVAILABLE: %s", name, m.key, e)
    return res


def cmd_auto(a, cfg):
    """Fully automatic multi-resolution calibration."""
    import numpy as np
    from .board import BoardSpec
    from .camera import ControlSession, Mode
    from .capture import run_capture_session
    auto_cfg = cfg.get("auto", {})
    names = a.profiles.split(",") if a.profiles else auto_cfg.get("profiles", ["4k_mjpg", "4k_yuyv", "1440p_mjpg"])
    profiles = {n: cfg["profiles"][n] for n in names}
    spec = BoardSpec.load(a.board or default_board())
    log.info("board: %s", spec.describe())
    if not spec.is_measured:
        log.warning("board spans not measured: intrinsics are still exact (print X/Y ratio is estimated from the "
                    "images), but mm verification will use the nominal scale. Measure with `camcal measure` when possible.")
    device = resolve_device(cfg, a.device)
    with __import__("camcal.v4l2", fromlist=["V4L2Device"]).V4L2Device(device) as d:
        log.info("camera: %s", d.info())
    pf = preflight(device, profiles)
    todo = [n for n in names if pf[n] is None]
    if not todo:
        raise SystemExit("no requested mode streams - check the camera / USB connection")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ROOT / "sessions" / f"auto_{stamp}"
    lock = dict(cfg.get("calibration_lock") or {})
    report = {"started": stamp, "device": device, "profiles": {}, "skipped": {n: pf[n] for n in names if pf[n]}}
    K_prev, size_prev = None, None
    stop_all = False
    with ControlSession(device, lock) as cs:          # ONE snapshot / restore around everything
        for i, name in enumerate(todo):
            if stop_all:
                report["profiles"][name] = {"skipped": "run stopped before this mode"}
                continue
            mode = Mode.from_dict(profiles[name])
            cc = _capture_cfg(cfg, a)
            cc.warmup_minutes = (a.warmup_min if a.warmup_min is not None else cc.warmup_minutes) if i == 0 \
                else float(auto_cfg.get("rewarm_minutes", 1.0))
            cc.warm_since = getattr(a, "warm_since", None) if i == 0 else None   # live-view time counts as warm-up
            _slow_mode_tweaks(cc, mode)
            K0 = None
            if K_prev is not None and abs(mode.width / mode.height - size_prev[0] / size_prev[1]) < 1e-3:
                K0 = np.array(K_prev) * np.array([[mode.width / size_prev[0]] * 3, [mode.height / size_prev[1]] * 3, [0, 0, 1]])
                K0[2, 2] = 1.0
            out = run_dir / mode.key
            log.info("=" * 70)
            log.info("[%d/%d] %s (%s): move the camera around the fixed board; capture is automatic", i + 1,
                     len(todo), name, mode.key)
            result = None
            for round_ in range(int(auto_cfg.get("max_rounds", 3))):
                sess = run_capture_session(device, mode, spec, out, cc, lock, auto=True, resume=round_ > 0,
                                           K0=K0, controls=cs, headless=a.headless,
                                           timeout_s=a.max_minutes * 60 if a.max_minutes else None)
                if sess.get("aborted"):
                    log.warning("run stopped by the user (ESC / window closed)")
                    stop_all = True
                    break
                if sess.get("n_captures", 0) < 10:
                    log.warning("%s: only %d captures - not enough to calibrate. Stopping here (not moving on to the "
                                "next resolution); run again when ready.", name, sess.get("n_captures", 0))
                    stop_all = True
                    break
                log.info("calibrating %s ... (about 1-2 minutes)", mode.key)
                result = run_calibration(out, cfg, board=a.board)
                log.info("%s grade %s, RMS %.4f px, issues: %s", mode.key, result["grade"], result["rms_px"], result["issues"])
                if result["grade"] == "PASS" or (result["grade"] == "WARN" and sess.get("complete")):
                    break
                if not sess.get("complete") and result["grade"] != "FAIL":
                    break                              # operator finished early on purpose; accept WARN
                cc.warmup_minutes = 0
                log.warning("%s needs more data (%s) - resuming capture", mode.key, result["issues"])
            if result:
                K_prev, size_prev = result["camera_matrix"], (mode.width, mode.height)
                report["profiles"][name] = {"mode": mode.key, "grade": result["grade"], "rms_px": result["rms_px"],
                                            "issues": result["issues"], "out": result["_out_dir"]}
    report["restore_diff"] = getattr(cs, "last_restore", {})
    (run_dir / "auto_report.json").write_text(json.dumps(report, indent=2, default=str))
    txt = summary_text(ROOT / "calibrations")
    (ROOT / "calibrations" / "SUMMARY.md").write_text("# Calibration summary\n\n```\n" + txt + "\n```\n")
    print("\n" + txt)
    if report["skipped"]:
        print("\nskipped (did not stream):", report["skipped"])
    print(f"\ncamera controls restored to their original values: {not report['restore_diff']}")


def cmd_preview(a, cfg):
    """Live view (no camera settings changed). START button / ENTER launches `auto`."""
    from .board import BoardSpec
    from .camera import Mode
    from .preview import run_preview
    spec = BoardSpec.load(a.board or default_board())
    device = resolve_device(cfg, a.device)
    mode = Mode.from_dict(cfg["profiles"][a.profile])
    log.info("live view: %s %s, board %s - click START CALIBRATION (or ENTER) when ready, Q to quit",
             device, mode.key, spec.name)
    import time as _t
    warm_since = _t.monotonic()          # the camera warms up while you look at the live view
    try:
        wm = a.warmup_min if a.warmup_min is not None else float(cfg.get("capture", {}).get("warmup_minutes", 10))
        start = run_preview(device, mode, spec, float(cfg.get("capture", {}).get("nominal_hfov_deg", 70.0)),
                            warmup_s=60.0 * wm, warm_since=warm_since, snapshot=a.snapshot, max_seconds=a.seconds)
    except KeyboardInterrupt:
        start = False
    if not start:
        log.info("preview closed")
        return
    if a.no_start:
        return
    log.info("START clicked -> automatic calibration")
    cmd_auto(argparse.Namespace(profiles=a.profiles, device=a.device, board=a.board, warmup_min=a.warmup_min,
                                views=None, max_minutes=None, headless=False, warm_since=warm_since), cfg)


def result_text(r: dict, mode_key: str) -> str:
    import numpy as np
    K = np.array(r["camera_matrix"]); D = np.array(r["dist_coeffs"]).ravel()
    hm = r.get("holdout_metric") or {}
    lines = [
        "", "=" * 72, f"CALIBRATION RESULT  {mode_key}   grade: {r['grade']}", "=" * 72,
        f"views used          : {r['n_views']}",
        f"reprojection error  : {r['rms_px']:.4f} px RMS",
        f"focal length fx, fy : {K[0, 0]:.2f}, {K[1, 1]:.2f} px",
        f"principal point     : {K[0, 2]:.2f}, {K[1, 2]:.2f} px",
        f"distortion ({r['distortion_model']}): " + " ".join(f"{v:+.6f}" for v in D),
        f"field of view       : {r['fov_deg']['horizontal']:.2f} x {r['fov_deg']['vertical']:.2f} deg",
    ]
    if hm:
        lines.append(f"measured accuracy   : {hm['holdout_mm_rms']:.3f} mm RMS (95%: {hm['holdout_mm_p95']:.3f} mm) "
                     f"on views not used for fitting, at ~{hm['holdout_distance_mm_median']:.0f} mm")
    b = r.get("bootstrap") or {}
    if b.get("uncertainty_px_max") is not None:
        lines.append(f"model uncertainty   : {b['uncertainty_px_max']:.3f} px worst case over the image")
    if r.get("issues"):
        lines.append("to improve          : " + "; ".join(r["issues"]))
    lines += [f"files               : {r['_out_dir']}/  (camera_{mode_key}.yaml / .json / _report.png)", "=" * 72]
    return "\n".join(lines)


def cmd_simple(a, cfg):
    """Hand-held capture with no guidance rules, then calibrate."""
    from .board import BoardSpec
    from .camera import Mode
    from .simple import run_simple
    spec = BoardSpec.load(a.board or default_board())
    device = resolve_device(cfg, a.device)
    mode = Mode.from_dict(cfg["profiles"][a.profile])
    tag = "still" if getattr(a, "still", False) else "simple"
    out = ROOT / "sessions" / f"{tag}_{dt.datetime.now():%Y%m%d_%H%M%S}" / mode.key
    cap = cfg.get("capture", {})
    log.info("simple capture %s on %s -> %s", mode.key, device, out)
    log.info("board fixed; move the camera slowly around it, pausing ~1 s at different spots/angles. It finishes by itself.")
    still = getattr(a, "still", False)
    # hand-held: short exposure (10 ms) against blur, more gain. still: camera at rest -> longer exposure, low gain
    res, n = run_simple(device, mode, spec, out, dict(cfg.get("calibration_lock") or {}),
                        float(cap.get("nominal_hfov_deg", 70.0)), max_exposure=330 if still else 100,
                        max_gain=30 if still else 80, still=still)
    log.info("camera settings restored. %d images in %s", n, out)
    if res != "done":
        log.info("quit without calibrating. To calibrate these images later: python3 -m camcal calibrate %s", out)
        return
    if n < 12:
        log.warning("only %d images - need at least 12 (30+ recommended). Run `camcal simple` again.", n)
        return
    log.info("calibrating %d images ... (about 1-2 minutes)", n)
    r = run_calibration(out, cfg, board=a.board)
    print(result_text(r, mode.key))


DERIVE_PLAN = [   # (reference calibration mode, test mode, expected mapping s, bx, by)
    ((3840, 2160, "MJPG", 25), (3840, 2160, "YUYV", 1), (1.0, 0.0, 0.0)),
    ((2560, 1440, "MJPG", 25), (2560, 1440, "YUYV", 1), (1.0, 0.0, 0.0)),
    ((3840, 2160, "MJPG", 25), (1280, 720, "MJPG", 60), (1 / 3, 0.0, 0.0)),
    ((3840, 2160, "MJPG", 25), (1280, 720, "YUYV", 15), (1 / 3, 0.0, 0.0)),
    ((1280, 960, "MJPG", 60), (640, 480, "MJPG", 60), (0.5, 0.0, 0.0)),
    ((1280, 960, "MJPG", 60), (640, 480, "YUYV", 30), (0.5, 0.0, 0.0)),
]


def cmd_derive(a, cfg):
    """Verify on the camera that further modes are exact re-samplings of calibrated ones; write their files."""
    from .board import BoardSpec
    from .camera import ControlSession, Mode
    from .derive import verify_mapping, write_derived
    spec = BoardSpec.load(a.board or default_board())
    device = resolve_device(cfg, a.device)
    lock = dict(cfg.get("calibration_lock") or {})
    lock.update({"auto_exposure": 1, "exposure_time_absolute": 150, "gain": 30})   # identical exposure in all modes
    rows = []
    only = set(a.only.split(",")) if getattr(a, "only", None) else None
    with ControlSession(device, lock) as cs:
        for ref_t, test_t, expect in DERIVE_PLAN:
            if only and Mode(*test_t).key not in only:
                continue
            ref, test = Mode(*ref_t), Mode(*test_t)
            ref_json = ROOT / "calibrations" / ref.key / f"camera_{ref.key}.json"
            if not ref_json.exists():
                log.warning("%s: reference %s not calibrated - skipped", test.key, ref.key)
                continue
            log.info("checking %s against %s ...", test.key, ref.key)
            try:
                v = verify_mapping(device, ref, test, spec, expect, cs=cs)
            except Exception as e:
                log.warning("%s: check failed: %s", test.key, e)
                rows.append((test.key, ref.key, "FAILED", str(e)))
                continue
            f = v["fitted"]
            ok = v["camera_still"] and v["matches_hardware_scaling"]
            msg = (f"s={f['s']:.5f} (expect {expect[0]:.5f}) b=({f['bx']:+.2f},{f['by']:+.2f}) "
                   f"residual {f['residual_rms_px']:.3f} px over {f['n']} corners; camera still: {v['camera_still']}")
            if ok:
                out = write_derived(ref_json, test, tuple(v["mapping_used"]), v, ROOT / "calibrations")
                rows.append((test.key, ref.key, "PASS", msg))
                log.info("%s VERIFIED -> %s", test.key, out)
            else:
                rows.append((test.key, ref.key, "NOT WRITTEN", msg))
                log.warning("%s does NOT match the expected re-sampling: %s", test.key, msg)
    print("\nmode              from             result        details")
    for r in rows:
        print(f"{r[0]:17s} {r[1]:16s} {r[2]:13s} {r[3]}")
    txt = summary_text(ROOT / "calibrations")
    (ROOT / "calibrations" / "SUMMARY.md").write_text("# Calibration summary\n\n```\n" + txt + "\n```\n")
    print("\n" + txt)


def cmd_verify(a, cfg):
    from .board import BoardSpec
    from .runtime import Calibration, CalibrationStore
    from .verify import run_verify
    if a.calib:
        calib = Calibration.load(a.calib)
    else:
        from .camera import Mode
        m = Mode.from_dict(cfg["profiles"][a.profile])
        calib = CalibrationStore(ROOT / "calibrations").for_mode(m.width, m.height, m.fourcc)
    spec = BoardSpec.load(a.board or default_board())
    if not spec.is_measured:
        log.warning("board not measured: metric errors are relative to the NOMINAL pitch")
    if a.simulate:
        from .capture import FakeCamera
        cam = FakeCamera(a.simulate, calib.mode)
    else:
        cam = calib.open_camera(resolve_device(cfg, a.device), strict=not a.force)
    try:
        res = run_verify(calib, spec, cam, ROOT / "calibrations" / "verify_log.json",
                         headless_frames=a.headless_frames)
        for r in res:
            print(json.dumps(r))
    finally:
        cam.release()


def cmd_summary(a, cfg):
    print(summary_text(ROOT / "calibrations"))


def cmd_selftest(a, cfg):
    sys.argv = ["synthetic", "--size", a.size, "--views", str(a.views)]
    sys.path.insert(0, str(ROOT))
    from tests.synthetic import main
    r = main()
    ok = abs(r["fx_err_pct"]) < 0.05 and r["undistort_map_err_px_max"] < 0.3 and r["rms_px"] < 0.1
    print("SELFTEST", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="camcal", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config" / "os08a10.yaml"))
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices")
    p = sub.add_parser("probe"); p.add_argument("--device")
    p = sub.add_parser("board"); p.add_argument("--preset", default="charuco_a3"); p.add_argument("--paper")
    p = sub.add_parser("measure"); p.add_argument("--board"); p.add_argument("--span-x", type=float, required=True)
    p.add_argument("--span-y", type=float, required=True)
    p = sub.add_parser("capture")
    p.add_argument("--profile", required=True); p.add_argument("--device"); p.add_argument("--board")
    p.add_argument("--warmup-min", type=float); p.add_argument("--views", type=int)
    p.add_argument("--manual", action="store_true", help="disable auto-capture (SPACE only)")
    p.add_argument("--simulate", help="folder of images to replay instead of a camera (dry run)")
    p.add_argument("--set", action="append", help="extra control lock key=value (repeatable)")
    p.add_argument("--no-calibrate", action="store_true"); p.add_argument("--model"); p.add_argument("--fast", action="store_true")
    p = sub.add_parser("calibrate"); p.add_argument("session"); p.add_argument("--board"); p.add_argument("--out")
    p.add_argument("--model"); p.add_argument("--fast", action="store_true", help="skip bootstrap")
    p = sub.add_parser("verify"); p.add_argument("--profile", default="4k_mjpg"); p.add_argument("--calib")
    p.add_argument("--device"); p.add_argument("--board"); p.add_argument("--simulate"); p.add_argument("--force", action="store_true")
    p.add_argument("--headless-frames", type=int, help=argparse.SUPPRESS)
    p = sub.add_parser("auto", help="fully automatic multi-resolution calibration")
    p.add_argument("--profiles", help="comma list, default from config auto.profiles")
    p.add_argument("--device"); p.add_argument("--board"); p.add_argument("--warmup-min", type=float)
    p.add_argument("--views", type=int)
    p.add_argument("--max-minutes", type=float, help="time cap per resolution (capture ends, then calibrates)")
    p.add_argument("--headless", action="store_true", help=argparse.SUPPRESS)
    p = sub.add_parser("export", help="write os08a10_camera_config.yaml: every camera detail + all calibrations")
    p.add_argument("--device")
    p = sub.add_parser("derive", help="verify YUYV / 720p / 480p modes against calibrated ones and write them")
    p.add_argument("--device"); p.add_argument("--board"); p.add_argument("--only", help="comma list of mode keys")
    p = sub.add_parser("simple", help="EASIEST: hand-held capture, ENTER -> calibration")
    p.add_argument("--profile", default="4k_mjpg"); p.add_argument("--device"); p.add_argument("--board")
    p.add_argument("--still", action="store_true", help=argparse.SUPPRESS)
    p = sub.add_parser("still", help="MOST ACCURATE: rest the camera for each shot; 8-frame averaged still images")
    p.add_argument("--profile", default="4k_mjpg"); p.add_argument("--device"); p.add_argument("--board")
    p = sub.add_parser("preview", help="live camera view with overlays; START button runs `auto`")
    p.add_argument("--profile", default="4k_mjpg"); p.add_argument("--device"); p.add_argument("--board")
    p.add_argument("--profiles", help="passed to auto when START is clicked")
    p.add_argument("--warmup-min", type=float, help="passed to auto when START is clicked")
    p.add_argument("--no-start", action="store_true", help="only view; START just closes the window")
    p.add_argument("--snapshot", help=argparse.SUPPRESS); p.add_argument("--seconds", type=float, help=argparse.SUPPRESS)
    sub.add_parser("summary")
    p = sub.add_parser("selftest"); p.add_argument("--size", default="1920x1080"); p.add_argument("--views", type=int, default=36)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    for noisy in ("fontTools", "matplotlib", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    cfg = load_cfg(a.config)
    {"devices": cmd_devices, "probe": cmd_probe, "board": cmd_board, "measure": cmd_measure, "capture": cmd_capture,
     "calibrate": cmd_calibrate, "verify": cmd_verify, "summary": cmd_summary, "selftest": cmd_selftest,
     "auto": cmd_auto, "preview": cmd_preview, "simple": cmd_simple, "derive": cmd_derive,
     "export": lambda a, c: print("written:", __import__("camcal.export", fromlist=["export"]).export(ROOT, device=a.device)),
     "still": lambda a, c: cmd_simple(argparse.Namespace(**{**vars(a), "still": True}), c)}[a.cmd](a, cfg)


if __name__ == "__main__":
    main()
