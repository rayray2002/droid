# glamor branch (USC GLAMOR lab Franka FR3, DROID setup)

Laptop side (`droid/`, `scripts/server`, `pyproject.toml`): upstream 33ae6a6 plus the working state of
the lab's laptop checkout on glamor-citrine as of 2026-10-19 (camera IDs, calibration, ZED SDK 5
reader changes, gripper metadata retry, aruco API update). Eval logs, caches and unrelated research
code from that checkout are not included.

Credentials are never committed: `droid/misc/parameters.py` reads `DROID_SUDO_PASSWORD` from the
environment; `ubuntu_pro_token` stays empty (only the NUC setup uses it).

`nuc/`: a record of the NUC (polymetis server, 169.254.202.1) as migrated on 2025-09-25: fairo
`0a01a7f` + `fairo_local_changes.patch` (FR3 limits, robot IP, C++17), libfranka `c5c66bb` (0.18.0)
+ `libfranka_local_changes.patch`, its conda env and bring-up notes. The NUC is a shared lab service;
this branch does not change it.

Used by segment-anysim as `third_party/droid` (docs/setup/robot.md there).
