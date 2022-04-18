"""Run entire conversion."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import timedelta

from tqdm import tqdm
from nwb_conversion_tools.utils.json_schema import load_dict_from_file
from nwb_conversion_tools.utils.json_schema import dict_deep_update
from spikeextractors import NeuroscopeRecordingExtractor

from buzsaki_lab_to_nwb.tingley_metabolic import (
    TingleyMetabolicConverter,
    load_subject_glucose_series,
    segment_glucose_series,
    get_session_datetime,
)

n_jobs = 20
progress_bar_options = dict(desc="Running conversion...", position=0, leave=False)
stub_test = True
conversion_factor = 0.195  # Intan

data_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/")
home_path = Path("/home/jovyan/")

metadata_path = Path(__file__) / "tingley_metabolic_metadata.yml"
subject_info_path = Path(__file__) / "tingley_metabolic_subject_info.yml"

if stub_test:
    nwb_output_path = home_path / Path("nwb_stub")
else:
    nwb_output_path = Path("/shared/catalystneuro/Buzsaki/TingleyD/nwb")
nwb_output_path.mkdir(exist_ok=True)


subject_list = ["CGM1", "CGM2"]  # This list will change based on what has finished transfering to the Hub
session_path_list = [subject_path for subject_path in data_path.iterdir() if subject_path.stem in subject_list]
if stub_test:
    nwbfile_list = [
        nwb_output_path / f"{subject_path.stem}_{session.stem}_stub.nwb"
        for subject_path in session_path_list
        for session in subject_path.iterdir()
    ]
else:
    nwbfile_list = [
        nwb_output_path / f"{subject_path.stem}_{session.stem}.nwb"
        for subject_path in session_path_list
        for session in subject_path.iterdir()
    ]

global_metadata = load_dict_from_file(metadata_path)
subject_info_table = load_dict_from_file(subject_info_path)


def convert_session(session_path, nwbfile_path):
    """Run coonversion."""
    print("----------------")
    print(session_path)
    print(nwbfile_path)

    conversion_options = dict()
    session_id = session_path.name

    xml_file_path = session_path / f"{session_id}.xml"
    raw_file_path = session_path / f"{session_id}.dat"
    lfp_file_path = session_path / f"{session_id}.lfp"

    aux_file_path = session_path / "auxiliary.dat"
    rhd_file_path = session_path / f"{session_id}.rhd"
    sleep_mat_file_path = session_path / f"{session_id}.SleepState.states.mat"

    # I know I'll need this for other sessions, just not yet
    # if not raw_file_path.is_file() and (session_path / f"{session_id}.dat_orig").is_file:
    #     raw_file_path = session_path / f"{session_id}.dat_orig"

    # raw_file_path = session_path / f"{session_id}.dat" if (session_path / f"{session_id}.dat").is_file() else

    subject_glucose_series = load_subject_glucose_series(session_path=session_path)
    this_ecephys_start_time = get_session_datetime(session_id=session_id)
    this_ecephys_stop_time = this_ecephys_start_time + timedelta(
        seconds=NeuroscopeRecordingExtractor(file_path=lfp_file_path).get_num_frames() / 1250.0
    )
    session_glucose_series, session_start_time = segment_glucose_series(
        this_ecephys_start_time=this_ecephys_start_time,
        this_ecephys_stop_time=this_ecephys_stop_time,
        glucose_series=subject_glucose_series,
    )
    source_data = dict(Glucose=dict(glucose_series=session_glucose_series))

    source_data = dict(
        NeuroscopeLFP=dict(file_path=str(lfp_file_path), gain=conversion_factor, xml_file_path=str(xml_file_path)),
    )
    conversion_options.update(NeuroscopeLFP=dict(stub_test=stub_test))

    if raw_file_path.is_file():
        source_data.update(
            NeuroscopeRecording=dict(
                file_path=str(raw_file_path), gain=conversion_factor, xml_file_path=str(xml_file_path)
            )
        )
        conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test))

    if aux_file_path.is_file() and rhd_file_path.is_file():
        source_data.update(Accelerometer=dict(dat_file_path=str(aux_file_path), rhd_file_path=str(rhd_file_path)))

    if sleep_mat_file_path.is_file():
        source_data.update(SleepStates=dict(mat_file_path=str(sleep_mat_file_path)))

    converter = TingleyMetabolicConverter(source_data=source_data)
    metadata = converter.get_metadata()
    metadata = dict_deep_update(metadata, global_metadata)
    metadata["NWBFile"].update(
        session_description=subject_info_table.get(
            metadata["NWBFile"]["Subject"]["subject_id"],
            "Consult Supplementary Table 1 from the publication for more information about this session.",
        ),
        session_start_time=session_start_time,
    )
    converter.run_conversion(
        nwbfile_path=str(nwbfile_path),
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
    print("Done with conversion!")


if n_jobs == 1:
    for session_path, nwbfile_path in tqdm(zip(session_path_list, nwbfile_list), **progress_bar_options):
        convert_session(session_path=session_path, nwbfile_path=nwbfile_path)
else:
    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = []
        for session_path, nwbfile_path in zip(session_path_list, nwbfile_list):
            futures.append(executor.submit(convert_session, session_path=session_path, nwbfile_path=nwbfile_path))
        completed_futures = tqdm(as_completed(futures), total=len(session_path_list), **progress_bar_options)
        for future in completed_futures:
            pass
