from pathlib import Path
from buzsaki_lab_to_nwb.huszar_hippocampus_dynamics import session_to_nwbfile

import concurrent.futures
import psutil
import json
import shutil


if __name__ == "__main__":
    # Parameters for conversion
    stub_test = False  # Converts a only a stub of the data for quick iteration and testing
    verbose = False
    write_electrical_series = True  # Write the electrical series to the NWB file
    iterator_opts = dict(buffer_gb=1.0, display_progress=verbose)

    output_dir_path = Path.home() / "final_conversion" / "HuszarR" # "conversion_nwb"
        
    project_root_path = Path("/shared/catalystneuro/HuszarR/optotagCA1")

    all_condition_paths = (path for path in project_root_path.iterdir() if path.is_dir())
    
    excluded = dict()

    session_dir_path_list = []

    for condition in all_condition_paths:
        condition_path = project_root_path / condition
        all_condition_subject_paths = (path for path in condition_path.iterdir() if path.is_dir())

        for subject_path in all_condition_subject_paths:
            all_subject_sessions_paths = (path for path in subject_path.iterdir() if path.is_dir())
            session_dir_path_list.extend(all_subject_sessions_paths)

    def worker(session_dir_path):
        try:
            session_to_nwbfile(
                session_dir_path,
                output_dir_path,
                stub_test=stub_test,
                write_electrical_series=write_electrical_series,
                verbose=verbose,
            )
        except Exception as e:
            print(f"ERROR ({str(session_dir_path.relative_to(project_root_path))}): {str(e)}")
            
    # Create a pool of worker processes
    num_physical_cores = psutil.cpu_count(logical=False)
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_physical_cores) as executor:
        executor.map(worker, session_dir_path_list)
