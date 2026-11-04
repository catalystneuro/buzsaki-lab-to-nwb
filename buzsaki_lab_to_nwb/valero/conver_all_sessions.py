"""Convert every session of the Valero et al. 2022 subjects (DANDI:000568), one at a time."""

from pathlib import Path

from buzsaki_lab_to_nwb.valero.convert_session import session_to_nwbfile

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "project_root_path", type=Path, help="the ValeroM folder (Drive copy, or unindexedSubjets on Globus)"
    )
    parser.add_argument("output_dir_path", type=Path)
    parser.add_argument("--no-raw", action="store_true", help="leave out the wide-band signal (.dat)")
    args = parser.parse_args()

    for subject in ["fCamk1", "fCamk2", "fCamk3", "fCamk5"]:
        # Session folders hold <session>.session.mat; on Drive, fCamk3 sess13 is nested in the sess12 folder
        session_files = sorted((args.project_root_path / subject).glob("**/*.session.mat"))
        for session_dir_path in [path.parent for path in session_files if path.stem == path.parent.name + ".session"]:
            if any(part in ("NonUsed", "NotUsed") for part in session_dir_path.parts):
                continue
            session_to_nwbfile(
                session_dir_path, args.output_dir_path, write_electrical_series=not args.no_raw, verbose=True
            )
