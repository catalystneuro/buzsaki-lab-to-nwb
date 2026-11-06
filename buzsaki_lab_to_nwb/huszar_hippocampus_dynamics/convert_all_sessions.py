"""Convert every session folder of HuszarR/optotagCA1 (e13 ... e16 / mouse / session), one at a time."""

import argparse
import traceback
from pathlib import Path

from buzsaki_lab_to_nwb.huszar_hippocampus_dynamics import session_to_nwbfile

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root_path", type=Path, help="the optotagCA1 folder")
    parser.add_argument("output_dir_path", type=Path)
    parser.add_argument("--stub", action="store_true")
    parser.add_argument("--no-lfp", action="store_true")
    parser.add_argument("--no-raw", action="store_true")
    args = parser.parse_args()

    session_dir_paths = sorted(path for path in args.project_root_path.glob("e*/*/*") if path.is_dir())
    for session_dir_path in session_dir_paths:
        try:
            session_to_nwbfile(
                session_dir_path,
                args.output_dir_path,
                stub_test=args.stub,
                write_lfp=not args.no_lfp,
                write_raw=not args.no_raw,
            )
        except Exception:
            print(f"ERROR ({session_dir_path.relative_to(args.project_root_path)}):\n{traceback.format_exc()}")
