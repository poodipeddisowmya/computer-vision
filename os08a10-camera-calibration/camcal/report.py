"""One-page visual calibration report (PNG)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def make_report(r: dict, views, res, out: Path) -> None:
    w, h = r["image_size"]
    fig, axs = plt.subplots(2, 3, figsize=(19, 10.5))
    fig.suptitle(f"{r['mode_key']}  |  {r['distortion_model']}  |  RMS {r['rms_px']:.4f} px  |  "
                 f"{r['n_views']} views  |  grade {r['grade']}", fontsize=14,
                 color={"PASS": "green", "WARN": "darkorange", "FAIL": "red"}[r["grade"]])

    # 1 residual scatter
    ax = axs[0, 0]
    allr = np.concatenate(res)
    ax.scatter(allr[:, 0], allr[:, 1], s=2, alpha=0.35)
    lim = max(0.5, float(np.percentile(np.abs(allr), 99.5)) * 1.2)
    ax.add_patch(plt.Circle((0, 0), r["rms_px"], fill=False, color="r", lw=1.2, label=f"RMS {r['rms_px']:.3f}px"))
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_aspect("equal")
    ax.set_title("reprojection residuals (px)"); ax.legend(loc="upper right"); ax.grid(alpha=0.3)

    # 2 per-view RMS
    ax = axs[0, 1]
    pv = [p["rms_px"] for p in r["per_view"]]
    ax.bar(range(len(pv)), pv, color="steelblue")
    ax.axhline(r["rms_px"], color="r", lw=1, label="overall RMS")
    ax.set_title("per-view RMS (px)"); ax.set_xlabel("view #"); ax.legend(); ax.grid(alpha=0.3, axis="y")

    # 3 coverage & residual magnitude in the image
    ax = axs[0, 2]
    pts = np.concatenate([v.img for v in views])
    mag = np.linalg.norm(allr, axis=1)
    sc = ax.scatter(pts[:, 0], pts[:, 1], c=mag, s=3, cmap="viridis", vmin=0, vmax=max(0.3, np.percentile(mag, 99)))
    ax.set_xlim(0, w); ax.set_ylim(h, 0); ax.set_aspect("equal")
    ax.set_title(f"corner coverage {r['coverage']['cells_covered_frac']:.0%} (colour = |residual| px)")
    fig.colorbar(sc, ax=ax, fraction=0.03)

    # 4 distortion displacement field
    ax = axs[1, 0]
    d = np.array(r["distortion"]["displacement_px"])
    im = ax.imshow(d, extent=(0, w, h, 0), cmap="magma")
    cs = ax.contour(np.linspace(0, w, d.shape[1]), np.linspace(0, h, d.shape[0]), d, colors="w", linewidths=0.6)
    ax.clabel(cs, fontsize=7, fmt="%.0f")
    ax.set_title(f"lens distortion displacement (px), max {r['distortion']['max_px']:.1f}")
    fig.colorbar(im, ax=ax, fraction=0.03)

    # 5 bootstrap uncertainty
    ax = axs[1, 1]
    b = r.get("bootstrap") or {}
    if b.get("uncertainty_px_grid"):
        u = np.array(b["uncertainty_px_grid"])
        im = ax.imshow(u, extent=(0, w, h, 0), cmap="inferno", vmin=0)
        ax.set_title(f"calibration uncertainty (bootstrap, px)  max {b['uncertainty_px_max']:.3f}")
        fig.colorbar(im, ax=ax, fraction=0.03)
    else:
        ax.text(0.5, 0.5, "bootstrap disabled", ha="center")

    # 6 text
    ax = axs[1, 2]
    ax.axis("off")
    K = np.array(r["camera_matrix"])
    s = r.get("std_dev", {})
    txt = [f"fx = {K[0, 0]:.3f} ± {s.get('fx', 0):.3f}", f"fy = {K[1, 1]:.3f} ± {s.get('fy', 0):.3f}",
           f"cx = {K[0, 2]:.3f} ± {s.get('cx', 0):.3f}", f"cy = {K[1, 2]:.3f} ± {s.get('cy', 0):.3f}", ""]
    txt += [f"{n} = {v:+.6f}" for n, v in zip(r["dist_coeffs_names"], r["dist_coeffs"])]
    f = r["fov_deg"]
    txt += ["", f"FOV H/V/D {f['horizontal']:.1f} / {f['vertical']:.1f} / {f['diagonal']:.1f} deg",
            f"tilt range {r['tilt']['tilt_deg_min']:.0f}..{r['tilt']['tilt_deg_max']:.0f} deg", ""]
    txt += [i[:95] for i in r["issues"]] or ["no issues"]
    ax.text(0, 1, "\n".join(txt), va="top", family="monospace", fontsize=9.5)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out, dpi=90)
    plt.close(fig)
