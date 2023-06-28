import concurrent.futures
from pathlib import Path

import psutil

from buzsaki_lab_to_nwb.valero.convert_session import session_to_nwbfile

if __name__ == "__main__":
    # Parameters for conversion
    stub_test = True  # Converts a only a stub of the data for quick iteration and testing
    verbose = True
    write_electrical_series = True  # Write the electrical series to the NWB file
    iterator_opts = dict(buffer_gb=1.0, display_progress=verbose)

    output_dir_path = Path.home() / "conversion_nwb"
    project_root_path = Path("/media/heberto/One Touch/Buzsaki/ValeroM/")

    subject_path = project_root_path / "fCamk1"
    subject_path = project_root_path / "fCamk2"
    subject_path_list = ["fCamk1", "fCamk2", "fcamk3", "fcamk5"]

    session_dir_path_list = []
    for subject in subject_path_list:
        subject_path = project_root_path / subject
        all_subject_sessions_paths = (path for path in subject_path.iterdir() if path.is_dir())
        session_dir_path_list.extend(all_subject_sessions_paths)

    def worker(session_dir_path):
        session_to_nwbfile(
            session_dir_path,
            output_dir_path,
            iterator_opts=iterator_opts,
            stub_test=stub_test,
            write_electrical_series=write_electrical_series,
            verbose=verbose,
        )

    # Create a pool of worker processes
    num_physical_cores = psutil.cpu_count(logical=False)
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_physical_cores) as executor:
        executor.map(worker, session_dirs)
