"""Print-ready vector PDF of the calibration target.

Every square / marker bit is an exact vector rectangle in millimetres, so the
printed geometry depends only on the printer (print at 100 %, "Actual size").
The page also carries:
  * 100 mm scale bars (horizontal and vertical) to check print scaling,
  * span ticks at the outer pattern edges for measuring the real pitch,
  * the board parameters needed by the pipeline.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402
import numpy as np  # noqa: E402

from .board import BoardSpec  # noqa: E402

PAPER_MM = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0),
            "LETTER": (279.4, 215.9), "TABLOID": (431.8, 279.4)}


def board_cell_grid(spec: BoardSpec) -> tuple[np.ndarray, float]:
    """Boolean black/white grid of the board on its finest common lattice.

    Returns (grid, cell_mm), where grid[r, c] is True for black.
    For ChArUco the board is rendered by OpenCV itself on a lattice where every
    square, marker and marker bit edge is an integer number of cells, then read
    back cell-by-cell, so the vector output matches OpenCV's layout exactly.
    """
    if spec.type == "checkerboard":
        r, c = np.indices((spec.squares_y, spec.squares_x))
        return ((r + c) % 2 == 0), spec.square_mm

    bits = spec.aruco_dict().markerSize + 2               # data bits + black border
    ratio = spec.marker_mm / spec.square_mm
    # Find the smallest cells-per-square N such that marker = ratio*N cells, the
    # margin (N - marker)/2 is integral and marker is divisible by `bits`.
    for n in range(bits, 4000):
        m = ratio * n
        if abs(m - round(m)) > 1e-9:
            continue
        m = int(round(m))
        if m % bits == 0 and (n - m) % 2 == 0:
            break
    else:
        raise ValueError("marker/square ratio does not fit an integer lattice; choose e.g. 0.75")
    px = 4  # pixels per lattice cell for the render
    board = spec.cv_charuco_board()
    img = board.generateImage((spec.squares_x * n * px, spec.squares_y * n * px), marginSize=0, borderBits=1)
    blocks = img.reshape(spec.squares_y * n, px, spec.squares_x * n, px)
    if not (blocks.min(axis=(1, 3)) == blocks.max(axis=(1, 3))).all():
        raise RuntimeError("OpenCV render does not align with lattice")
    grid = blocks[:, 0, :, 0] < 128
    return grid, spec.square_mm / n


def _grid_path(grid: np.ndarray, cell: float, x0: float, y0: float) -> MPath:
    """Single compound path (horizontal runs) -> no hairline seams between cells."""
    verts, codes = [], []
    for r in range(grid.shape[0]):
        row = grid[r]
        c = 0
        while c < len(row):
            if not row[c]:
                c += 1
                continue
            s = c
            while c < len(row) and row[c]:
                c += 1
            xa, xb = x0 + s * cell, x0 + c * cell
            ya, yb = y0 + r * cell, y0 + (r + 1) * cell
            verts += [(xa, ya), (xb, ya), (xb, yb), (xa, yb), (xa, ya)]
            codes += [MPath.MOVETO, MPath.LINETO, MPath.LINETO, MPath.LINETO, MPath.CLOSEPOLY]
    return MPath(verts, codes)


def _ruler(ax, x, y, length, vertical=False, fs=5):
    lw = 0.25
    if vertical:
        ax.add_patch(Rectangle((x, y), 0.25, length, color="k", lw=0))
        for mm in range(0, int(length) + 1):
            t = 3.0 if mm % 10 == 0 else (2.0 if mm % 5 == 0 else 1.2)
            ax.plot([x, x - t], [y + mm, y + mm], color="k", lw=lw, solid_capstyle="butt")
            if mm % 10 == 0:
                ax.text(x - 3.6, y + mm, f"{mm}", fontsize=fs, ha="right", va="center")
    else:
        ax.add_patch(Rectangle((x, y), length, 0.25, color="k", lw=0))
        for mm in range(0, int(length) + 1):
            t = 3.0 if mm % 10 == 0 else (2.0 if mm % 5 == 0 else 1.2)
            ax.plot([x + mm, x + mm], [y, y + t], color="k", lw=lw, solid_capstyle="butt")
            if mm % 10 == 0:
                ax.text(x + mm, y + 4.6, f"{mm}", fontsize=fs, ha="center", va="top")


def make_board_pdf(spec: BoardSpec, paper: str, out_pdf: str | Path, preview_png: str | Path | None = None,
                   top_mm: float | None = None) -> dict:
    W, H = PAPER_MM[paper.upper()]
    bw, bh = spec.squares_x * spec.square_mm, spec.squares_y * spec.square_mm
    if bw + 2 * 12 > W or bh + 30 > H:
        raise ValueError(f"board {bw}x{bh} mm does not fit on {paper} landscape with margins")
    x0 = round((W - bw) / 2.0, 3)
    y0 = top_mm if top_mm is not None else round(max(13.0, (H - bh - 26.0) / 2.0), 3)

    plt.rcParams["pdf.fonttype"] = 42
    fig = plt.figure(figsize=(W / 25.4, H / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)           # y down, millimetres
    ax.set_aspect("equal")
    ax.axis("off")

    grid, cell = board_cell_grid(spec)
    ax.add_patch(PathPatch(_grid_path(grid, cell, x0, y0), facecolor="black", edgecolor="none", lw=0))

    # --- span ticks at outer pattern edges (for caliper / steel-rule measurement)
    tl, gap = 5.0, 1.0
    for xx in (x0, x0 + bw):
        ax.plot([xx, xx], [y0 - gap - tl, y0 - gap], color="k", lw=0.4, solid_capstyle="butt")
    for yy in (y0, y0 + bh):
        ax.plot([x0 - gap - tl, x0 - gap], [yy, yy], color="k", lw=0.4, solid_capstyle="butt")
    ax.text(x0 + bw / 2, y0 - gap - 2.0, f"X span (tick to tick) nominal {bw:.2f} mm  ->  measure & enter",
            fontsize=5.5, ha="center", va="bottom")
    ax.text(x0 - gap - 3.0, y0 + bh / 2, f"Y span nominal {bh:.2f} mm", fontsize=5.5, rotation=90,
            ha="right", va="center")

    # --- 100 mm scale bars
    ry = y0 + bh + 5.0
    _ruler(ax, x0, ry, 100.0)
    vx = min(W - 4.0, x0 + bw + 0.5 * (W - x0 - bw) + 2.0)
    vlen = min(100.0, bh)
    _ruler(ax, vx, y0, vlen, vertical=True)

    kind = (f"ChArUco {spec.dictionary}  |  marker {spec.marker_mm} mm" if spec.type == "charuco"
            else "Checkerboard")
    lines = [
        f"{kind}  |  {spec.squares_x} x {spec.squares_y} squares  |  square {spec.square_mm} mm  |  "
        f"{spec.n_corners} inner corners  |  OpenCV {cv2.__version__}  |  board id: {spec.name}",
        "PRINT AT 100 % / 'Actual size' - disable 'Fit to page'. Laser printer, matte paper, highest quality.",
        "Check: the 100 mm scale bars must measure 100.0 mm. Mount perfectly flat (glass / aluminium composite). "
        "Then measure X and Y spans tick-to-tick.",
    ]
    ty = ry + 7.5
    for i, t in enumerate(lines):
        ax.text(x0 + 104.0 if i == 0 else x0 + 104.0, ty + i * 3.4 - 6.0, t, fontsize=5.2, ha="left", va="top")

    out_pdf = Path(out_pdf)
    fig.savefig(out_pdf, format="pdf")
    if preview_png:
        fig.savefig(preview_png, dpi=150)
    plt.close(fig)
    return {"paper": paper, "page_mm": (W, H), "board_origin_mm": (x0, y0), "board_mm": (bw, bh),
            "lattice_cell_mm": cell}


def verify_pdf_detects(spec: BoardSpec, pdf: str | Path, dpi: int = 200) -> tuple[int, int]:
    """Rasterise the PDF with pdftoppm and run the detector: proves the print is decodable."""
    import subprocess
    import tempfile

    from .board import BoardDetector

    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", str(pdf), f"{td}/p"], check=True)
        png = sorted(Path(td).glob("p*.png"))[0]
        img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    det = BoardDetector(spec).detect(img)
    return det.n, spec.n_corners
