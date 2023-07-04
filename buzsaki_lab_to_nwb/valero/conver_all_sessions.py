import concurrent.futures
import time
from pathlib import Path

import psutil

from buzsaki_lab_to_nwb.valero.convert_session import session_to_nwbfile

if __name__ == "__main__":
    # Parameters for conversion
    stub_test = False  # Converts a only a stub of the data for quick iteration and testing
    verbose = True
    run_in_parallel = False
    write_electrical_series = False  # Write the electrical series to the NWB file
    iterator_opts = dict(buffer_gb=1.0, display_progress=verbose)

    output_dir_path = Path.home() / "conversion_nwb" / "no_raw_data"
    output_dir_path.mkdir(parents=True, exist_ok=True)
    project_root_path = Path("/media/heberto/One Touch/Buzsaki/ValeroM/")

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

    if verbose:
        start_time = time.time()

    if run_in_parallel:
        # Create a pool of worker processes
        num_physical_cores = psutil.cpu_count(logical=False)
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_physical_cores) as executor:
            executor.map(worker, session_dir_path_list)
    else:
        for session_dir_path in session_dir_path_list:
            worker(session_dir_path)

    if verbose:
        end_time = time.time()
        conversion_time = end_time - start_time
        print("\n -----------------------------")
        print(f"All files are converted.  Done in {conversion_time / 60.0 :,.2f} minutes!")
