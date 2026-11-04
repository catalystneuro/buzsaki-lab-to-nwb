"""Convert every session of the Valero et al. 2022 subjects (DANDI:000568), one at a time."""

from pathlib import Path

from buzsaki_lab_to_nwb.valero.convert_session import session_to_nwbfile

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root_path", type=Path, help="the Globus ValeroM/unindexedSubjets folder")
    parser.add_argument("output_dir_path", type=Path)
    parser.add_argument("--signals-root", type=Path, help="root with <session>/<session>.lfp and .dat (2023 copy)")
    parser.add_argument("--no-raw", action="store_true", help="leave out the wide-band signal (.dat)")
    args = parser.parse_args()

    for subject in ["fCamk1", "fCamk2", "fCamk3", "fCamk5"]:
        for session_dir_path in sorted(path for path in (args.project_root_path / subject).iterdir() if path.is_dir()):
            if not (session_dir_path / f"{session_dir_path.name}.session.mat").is_file():
                continue  # e.g. NonUsed/ and NotUsed/
            session_to_nwbfile(
                session_dir_path,
                args.output_dir_path,
                write_electrical_series=not args.no_raw,
                signals_folder_path=args.signals_root / session_dir_path.name if args.signals_root else None,
                verbose=True,
            )
