"""Write ONE file with everything a vision project needs about this camera.

    python3 -m camcal export            -> os08a10_camera_config.yaml

Camera / sensor / lens facts, USB identity, every video mode (with its calibration:
camera matrix, distortion, undistortion matrices, FOV, mm/px, measured accuracy),
all camera controls (ranges, defaults, the camera's normal values) and the rules
that keep the calibration valid. Re-run after any recalibration.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import yaml

SENSOR = {
    "name": "OmniVision OS08A10", "type": "BSI CMOS, colour (Bayer)", "shutter": "rolling",
    "optical_format": "1/1.8 inch", "pixel_size_um": 2.0, "active_pixels": [3840, 2160],
    "active_area_mm": [7.68, 4.32], "chief_ray_angle_deg": 11,
}
# How the module's ISP produces each mode from the sensor (measured on this camera)
MODE_FACTS = {
    "3840x2160_MJPG": {"sensor_region": "full 3840x2160", "scale": 1.0, "fps": 25, "use": "PRIMARY precision mode (live)"},
    "3840x2160_YUYV": {"sensor_region": "full 3840x2160", "scale": 1.0, "fps": 1, "use": "uncompressed stills, static scenes / tripod"},
    "2560x1440_MJPG": {"sensor_region": "full 3840x2160", "scale": 2 / 3, "fps": 25, "use": "precision / speed balance"},
    "2560x1440_YUYV": {"sensor_region": "full 3840x2160", "scale": 2 / 3, "fps": 1, "use": "uncompressed stills"},
    "1280x960_MJPG": {"sensor_region": "centre crop 2880x2160", "scale": 1280 / 2880, "fps": 60, "use": "fast, narrower view, cleanest corners"},
    "1280x720_MJPG": {"sensor_region": "full 3840x2160", "scale": 1 / 3, "fps": 60, "use": "fast, full view, close range only for sub-mm"},
    "1280x720_YUYV": {"sensor_region": "full 3840x2160", "scale": 1 / 3, "fps": 15, "use": "uncompressed, close range"},
    "640x480_MJPG": {"sensor_region": "centre crop 2880x2160", "scale": 640 / 2880, "fps": 60, "use": "preview / positioning only"},
    "640x480_YUYV": {"sensor_region": "centre crop 2880x2160", "scale": 640 / 2880, "fps": 30, "use": "preview / positioning only"},
}
NOT_AVAILABLE = {"1920x1080_MJPG": "advertised by the camera but delivers no frames (firmware)",
                 "1920x1080_YUYV": "advertised by the camera but delivers no frames (firmware)"}


def _r(x, n=6):
    if isinstance(x, float):
        return round(x, n)
    if isinstance(x, list):
        return [_r(v, n) for v in x]
    if isinstance(x, dict):
        return {k: _r(v, n) for k, v in x.items()}
    return x


def _mode_block(key: str, r: dict, rel: str) -> dict:
    K = r["camera_matrix"]
    D = r["dist_coeffs"]
    w, h = r["image_size"]
    facts = MODE_FACTS.get(key, {})
    derived = r.get("derived", False)
    hm = r.get("holdout_metric") or (r.get("derived_from", {}) or {}).get("reference_holdout_metric", {})
    names = ["k1", "k2", "p1", "p2", "k3", "k4", "k5", "k6"]
    blk = {
        "resolution": [w, h], "pixel_format": r["mode"].get("fourcc"), "fps": facts.get("fps", r["mode"].get("fps")),
        "sensor_region": facts.get("sensor_region"), "scale_from_sensor": _r(facts.get("scale")),
        "recommended_use": facts.get("use"),
        "calibration": {
            "grade": r.get("grade"),
            "method": (f"derived from {r['derived_from']['mode']} (re-sampling verified on the camera, residual "
                       f"{r['verification']['fitted']['residual_rms_px']:.3f} px)") if derived
                      else f"full calibration, {r.get('n_views')} images, board self-calibration "
                           f"{'applied' if (r.get('board_refinement') or {}).get('applied') else 'not needed'}",
            "date": r.get("created") or r.get("calibration_time"),
            "file_opencv_yaml": f"{rel}/camera_{key}.yaml", "file_json": f"{rel}/camera_{key}.json",
            "distortion_model": r["distortion_model"],
            "camera_matrix": _r(K, 4),
            "fx": _r(K[0][0], 3), "fy": _r(K[1][1], 3), "cx": _r(K[0][2], 3), "cy": _r(K[1][2], 3),
            "dist_coeffs": _r(list(D), 8),
            "dist_coeffs_named": {n: _r(v, 8) for n, v in zip(names, D)},
            "new_camera_matrix_alpha0_no_black_border": _r(r.get("new_camera_matrix_alpha0"), 4),
            "new_camera_matrix_alpha1_keep_all_pixels": _r(r.get("new_camera_matrix_alpha1"), 4),
            "field_of_view_deg": _r({k: r["fov_deg"][k] for k in ("horizontal", "vertical", "diagonal") if k in r["fov_deg"]}, 2),
            "focal_length_mm_equivalent": _r(K[0][0] * SENSOR["pixel_size_um"] / 1000.0 / facts.get("scale", 1.0), 3)
            if facts.get("scale") else None,
            "reprojection_rms_px": _r(r.get("rms_px"), 4),
            "accuracy_mm": {"rms": _r(hm.get("holdout_mm_rms"), 3), "p95": _r(hm.get("holdout_mm_p95"), 3),
                            "at_distance_mm": _r(hm.get("holdout_distance_mm_median"), 0),
                            "note": "measured on views never used for fitting" + (" (of the reference mode)" if derived else "")},
            "mm_per_px": {f"{z}mm": _r((v["mm_per_px_x"] + v["mm_per_px_y"]) / 2, 4)
                          for z, v in (r.get("metric_resolution") or {}).items()},
            "field_of_view_mm": {f"{z}mm": _r(v["field_of_view_mm"], 1) for z, v in (r.get("metric_resolution") or {}).items()},
        },
    }
    return blk


def build(root: Path, device: str | None = None) -> dict:
    cal_root = root / "calibrations"
    modes = {}
    for d in sorted(cal_root.iterdir()):
        j = d / f"camera_{d.name}.json"
        if d.is_dir() and j.exists():
            modes[d.name] = _mode_block(d.name, json.loads(j.read_text()), f"calibrations/{d.name}")
    order = ["3840x2160_MJPG", "3840x2160_YUYV", "2560x1440_MJPG", "2560x1440_YUYV", "1280x960_MJPG",
             "1280x720_MJPG", "1280x720_YUYV", "640x480_MJPG", "640x480_YUYV"]
    modes = {k: modes[k] for k in order if k in modes} | {k: v for k, v in modes.items() if k not in order}

    identity, controls, formats = {}, {}, []
    try:
        from .v4l2 import V4L2Device, control_dump, find_device
        dev = device or find_device("HJ 4K Camera")
        with V4L2Device(dev) as v:
            identity = v.info()
            formats = [{"fourcc": f["fourcc"], "sizes": [f"{s['width']}x{s['height']} @ {s.get('fps')}" for s in f["sizes"]]}
                       for f in v.formats()]
            for k, c in control_dump(v.controls()).items():
                e = {"range": [c["minimum"], c["maximum"]], "step": c["step"], "default": c["default"],
                     "normal_value": c["value"], "type": c["type"]}
                if c.get("menu"):
                    e["menu"] = {int(a): b for a, b in c["menu"].items()}
                controls[k] = e
    except Exception as e:                       # camera unplugged: everything else is still written
        identity = {"note": f"camera not reachable when this file was generated: {e}"}

    ref = modes.get("3840x2160_MJPG", {}).get("calibration", {})
    cfg = {
        "_about": {
            "file": "Complete OS08A10 camera description for vision projects - generated by `python3 -m camcal export`",
            "generated": dt.datetime.now().isoformat(timespec="seconds"),
            "units": "pixels unless stated; camera_matrix = [[fx,0,cx],[0,fy,cy],[0,0,1]]; OpenCV distortion order k1,k2,p1,p2,k3",
        },
        "camera": {
            "model": "OS08A10 8MP USB camera module (Waveshare OS08A10 8MP USB Camera (A))",
            "sensor": SENSOR,
            "lens": {
                "type": "fixed-focus M12 lens (no electronic focus / zoom)",
                "focal_length_mm_calibrated": ref.get("focal_length_mm_equivalent"),
                "field_of_view_deg_full_frame": ref.get("field_of_view_deg"),
                "distortion": "barrel (k1 about -0.17), about 150 px at the 4K image corners",
            },
            "interface": {"bus": "USB 2.0 (480 Mbit/s), UVC", "bridge": "Sonix Technology 0c45:636d",
                          "v4l2_card_name": identity.get("card"), "usb_vendor_product": f"{identity.get('usb_idVendor')}:{identity.get('usb_idProduct')}",
                          "usb_serial": identity.get("usb_serial"), "usb_port_path": identity.get("usb_port_path"),
                          "device_now": identity.get("path"), "driver": identity.get("driver"),
                          "find_it_by": "card name 'HJ 4K Camera' (device number can change; see camcal.v4l2.find_device)"},
            "formats_advertised": formats,
        },
        "modes": modes,
        "modes_not_available": NOT_AVAILABLE,
        "mode_choice_for_sub_mm": {
            "rule": "measurement uncertainty ~ 0.25-0.5 px on real parts; need <= 0.2-0.25 mm/px for 0.5 mm",
            "3840x2160_MJPG": "sub-mm up to ~1 m",
            "2560x1440_MJPG": "sub-mm up to ~60-70 cm",
            "1280x960_MJPG": "sub-mm up to ~45-50 cm (narrower view, 60 fps)",
            "1280x720_MJPG": "sub-mm only below ~35 cm",
        },
        "camera_settings": {
            "controls": controls,
            "geometry_relevant_controls": "none - the module exposes no zoom / pan / tilt / focus; geometry depends only "
                                          "on the MODE (resolution + format) and the physical lens",
            "recommended_for_measurement": {
                "white_balance_automatic": 0, "exposure_dynamic_framerate": 0, "backlight_compensation": 0,
                "auto_exposure": "1 (manual) with exposure_time_absolute as short as the light allows (<= 200 = 20 ms; "
                                 "units of 100 us) and the lowest gain that gives white board areas ~200/255",
                "note": "exposure / gain / white balance do NOT change the calibration; they change image quality",
            },
            "settings_policy": "calibration tools snapshot all controls, apply their lock, and restore the original "
                               "values afterwards (also on Ctrl-C) - other projects see the camera unchanged",
        },
        "rules_to_keep_calibration_valid": [
            "Use each calibration ONLY with its own resolution AND pixel format (the mode key, e.g. 3840x2160_MJPG).",
            "Never touch or turn the lens - lock the M12 thread (thread-lock / glue) for production.",
            "Let the camera stream ~10 min before precision measurement (focal length drifts while warming up).",
            "Do not resize / stretch frames; crop or pad only, and shift cx / cy by the crop or pad offset.",
            "Re-verify periodically (e.g. weekly, or after any knock) with a known reference object; recalibrate if > 0.2 mm off.",
            "Before production sign-off: measure 3-5 known lengths at the working distance (centre and edges); all errors < ~0.3 mm.",
        ],
        "usage": {
            "python_camcal": "from camcal.runtime import CalibrationStore; cal = CalibrationStore('calibrations').for_frame(frame)  "
                             "# picks the mode by frame size (pass fourcc='YUYV' for YUYV); cal.undistort_image(frame), "
                             "cal.undistort_points(pts), cal.pixels_to_plane(pts, rvec, tvec), cal.mm_per_px(z_mm)",
            "plain_opencv": "fs = cv2.FileStorage('calibrations/3840x2160_MJPG/camera_3840x2160_MJPG.yaml', cv2.FILE_STORAGE_READ); "
                            "K = fs.getNode('camera_matrix').mat(); D = fs.getNode('distortion_coefficients').mat(); "
                            "und = cv2.undistort(frame, K, D)",
            "board_used": "ChArUco A3, 14x10 squares, 25 mm squares, 18.75 mm markers, DICT_4X4_100 (boards/charuco_a3.pdf)",
        },
    }
    return cfg


class _Dumper(yaml.SafeDumper):
    """Readable YAML: no anchors/aliases, numeric lists and matrix rows on one line."""
    def ignore_aliases(self, data):
        return True


def _list_rep(dumper, data):
    flow = all(isinstance(v, (int, float, str)) and not (isinstance(v, str) and len(v) > 40) for v in data) and len(data) <= 8
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


_Dumper.add_representer(list, _list_rep)


def export(root: Path, out: Path | None = None, device: str | None = None) -> Path:
    out = out or (root / "os08a10_camera_config.yaml")
    cfg = build(root, device)
    header = ("# OS08A10 camera - complete configuration and calibration for vision projects\n"
              "# Regenerate with:  python3 -m camcal export\n\n")
    out.write_text(header + yaml.dump(cfg, Dumper=_Dumper, sort_keys=False, width=160, allow_unicode=True))
    return out
