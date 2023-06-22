from pathlib import Path

from buzsaki_lab_to_nwb.valero.convert_session import session_to_nwbfile

if __name__ == "__main__":
    # Parameters for conversion
    stub_test = True  # Converts a only a stub of the data for quick iteration and testing
    verbose = True
    write_electrical_series = True  # Write the electrical series to the NWB file
    output_dir_path = Path.home() / "conversion_nwb"
    project_root_path = Path("/media/heberto/One Touch/Buzsaki/ValeroM/")

    subject_path = project_root_path / "fCamk1"
    subject_path = project_root_path / "fCamk2"
    subject_path_list = ["fCamk1", "fCamk2"]
    for subject in subject_path_list:
        subject_path = project_root_path / subject
        all_subject_sessions_paths = (path for path in subject_path.iterdir() if path.is_dir())

        for session_dir_path in all_subject_sessions_paths:
            session_to_nwbfile(
                session_dir_path,
                output_dir_path,
                stub_test=stub_test,
                write_electrical_series=write_electrical_series,
                verbose=verbose,
            )
