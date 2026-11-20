#!/usr/bin/env python3
"""Print a coarse top-down map of the Baylands Fuel model in WORLD coordinates (meters from the world origin).

Run on the machine that has the Gazebo Fuel cache. It reads the meshes, so nothing large is sent anywhere.
  pip install trimesh numpy pycollada    (pycollada only if the meshes are .dae)
  python3 tools/baylands_map.py                       # finds the model in ~/.gz and ~/.ignition
  python3 tools/baylands_map.py /path/to/baylands/1   # or give the folder
  python3 tools/baylands_map.py --cell 40 > map.txt   # 40 m cells, send map.txt back

World point = model-local point + (205, 155, -1), from baylands.sdf. World is ENU: east_m = X, north_m = Y.
Map legend: '.' = no geometry, ':' = low ground (under 3 m above the lowest point), '#' = tall geometry
(3 m or more above local ground: buildings, bridge, trees). Row labels are north_m, column labels are east_m.
Check any coordinate in Gazebo before using it. The offset and axes here are read from the SDF, not tested on the real mesh.
"""
import argparse, glob, os, sys
import numpy as np
import trimesh

OFFSET = np.array([205.0, 155.0, -1.0])   # from baylands.sdf, the include pose of 'park'


def find_model():
    pats = [os.path.expanduser(p) for p in (
        "~/.gz/fuel/fuel.gazebosim.org/openrobotics/models/baylands/*",
        "~/.ignition/fuel/fuel.gazebosim.org/openrobotics/models/baylands/*")]
    for p in pats:
        hits = sorted(glob.glob(p))
        if hits:
            return hits[-1]
    sys.exit("Baylands model not found. Pass the folder path as an argument.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--cell", type=float, default=50.0, help="map cell size in meters")
    ap.add_argument("--tall", type=float, default=3.0, help="height above local ground counted as '#'")
    a = ap.parse_args()
    root = a.folder or find_model()
    files = [f for ext in ("obj", "dae", "stl", "glb", "gltf", "ply",
                           "OBJ", "DAE", "STL", "GLB", "GLTF", "PLY")
             for f in glob.glob(os.path.join(root, "**", f"*.{ext}"), recursive=True)]
    print(f"model folder: {root}\nmesh files: {len(files)}", file=sys.stderr)
    pts = []
    for f in files:
        try:
            m = trimesh.load(f, force="mesh")
            if isinstance(m, trimesh.Scene):
                m = trimesh.util.concatenate(m.dump())
            v = np.asarray(m.vertices)
            if len(v) and m.area > 0:
                # sample the surface too, so big flat triangles (ground) are not just their corners
                v = np.vstack([v, m.sample(min(400000, int(m.area) + 1000))])
            if len(v):
                print(f"{os.path.relpath(f, root)}: local bounds min {v.min(0).round(1)} max {v.max(0).round(1)}", file=sys.stderr)
                pts.append(v)
        except Exception as e:
            print(f"skip {f}: {e}", file=sys.stderr)
    if not pts:
        sys.exit("no meshes could be read")
    v = np.vstack(pts) + OFFSET           # world coordinates, assumes no rotation/scale in the model SDF
    ground = np.percentile(v[:, 2], 5)
    x0, x1 = np.floor(v[:, 0].min() / a.cell), np.ceil(v[:, 0].max() / a.cell)
    y0, y1 = np.floor(v[:, 1].min() / a.cell), np.ceil(v[:, 1].max() / a.cell)
    nx, ny = int(x1 - x0), int(y1 - y0)
    top = np.full((ny, nx), -np.inf)
    ix = np.clip(((v[:, 0] / a.cell) - x0).astype(int), 0, nx - 1)
    iy = np.clip(((v[:, 1] / a.cell) - y0).astype(int), 0, ny - 1)
    np.maximum.at(top, (iy, ix), v[:, 2])
    print(f"world extent: east_m {v[:,0].min():.0f}..{v[:,0].max():.0f}, north_m {v[:,1].min():.0f}..{v[:,1].max():.0f}, "
          f"z {v[:,2].min():.1f}..{v[:,2].max():.1f}, ground about {ground:.1f}, cell {a.cell:.0f} m")
    print("columns = east_m starting at", int(x0 * a.cell), "step", int(a.cell))
    for r in range(ny - 1, -1, -1):
        row = "".join("." if not np.isfinite(t) else ("#" if t - ground >= a.tall else ":") for t in top[r])
        print(f"{int((y0 + r) * a.cell):6d} | {row}")


if __name__ == "__main__":
    main()
