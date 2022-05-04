"""Run entire conversion."""
from pathlib import Path
from datetime import timedelta
from warnings import simplefilter

from tqdm import tqdm
from nwb_conversion_tools.tools.data_transfers import (
    dandi_upload,
    estimate_total_conversion_runtime,
    estimate_s3_conversion_cost,
    get_globus_dataset_content_sizes,
    transfer_globus_content,
)
from nwb_conversion_tools.utils import load_dict_from_file, dict_deep_update
from spikeextractors import NeuroscopeRecordingExtractor

from buzsaki_lab_to_nwb.tingley_metabolic import TingleyMetabolicConverter, get_session_datetime

buzsaki_globus_endpoint_id = "188a6110-96db-11eb-b7a9-f57b2d55370d"
hub_globus_endpoint_id = "52de6745-40b8-4d2c-9a0b-610874c564f5"
dandiset_id = "000233"

base_buzsaki_path = Path("TingleyD/Tingley2021_ripple_glucose_paper/")
subject = "CGM36"
all_content = get_globus_dataset_content_sizes(
    globus_endpoint_id=buzsaki_globus_endpoint_id, path=(base_buzsaki_path / subject).as_posix()
)
sessions = list(set([Path(x).parent.name for x in all_content]) - set([""]))

session_idx = 1
session_id = sessions[session_idx]
assert f"{session_id}/{session_id}.lfp" in all_content, "Skip session_idx {session_idx} - bad session!"
content_to_attempt_transfer = [
    f"{session_id}/{session_id}.xml",
    # f"{session_id}/{session_id}.dat",
    f"{session_id}/{session_id}.lfp",
    f"{session_id}/auxiliary.dat",
    f"{session_id}/info.rhd",
    f"{session_id}/{session_id}.SleepState.states.mat",
    f"{session_id}/",
]
content_to_attempt_transfer.extend([x for x in all_content if Path(x).suffix == ".csv"])
# Ripple files are a little trickier, can have multiple text forms
content_to_attempt_transfer.extend(
    [
        x
        for x in all_content
        if Path(x).parent.name == session_id
        for suffix in Path(x).suffixes
        if "ripples" in suffix.lower()
    ]
)
content_to_transfer = [x for x in content_to_attempt_transfer if x in all_content]

content_to_transfer_size = sum([all_content[x] for x in content_to_transfer])
total_time = estimate_total_conversion_runtime(total_mb=content_to_transfer_size / 1e6)
total_cost = estimate_s3_conversion_cost(total_mb=content_to_transfer_size / 1e6)
y_n = input(
    f"Converting session {session_id} will cost an estimated ${total_cost} and take {total_time/3600} hours. "
    "Continue? (y/n)"
)
assert y_n.lower() == "y"


progress_bar_options = dict(desc="Running conversion...", position=0, leave=False)
stub_test = False
conversion_factor = 0.195  # Intan
buffer_gb = 50
# note that on DANDIHub, max number of actual I/O operations on processes seems limited to 8-10,
# so total mem isn't technically buffer_gb * n_jobs

data_path = Path("/shared/catalystneuro/TingleyD/")
home_path = Path("/home/jovyan/")

data_path = Path("E:/BuzsakiData/TingleyD")
home_path = Path("E:/BuzsakiData/TingleyD/")

metadata_path = Path(__file__).parent / "tingley_metabolic_metadata.yml"
subject_info_path = Path(__file__).parent / "tingley_metabolic_subject_info.yml"


subject_list = [
    "CGM4"
]  # [1,2,3,4,30,31,32,36,37,39]]  # This list will change based on what has finished transfering to the Hub
session_path_list = [
    session_path
    for subject_path in data_path.iterdir()
    if subject_path.is_dir() and subject_path.stem in subject_list
    for session_path in subject_path.iterdir()
    if session_path.is_dir()
]


if stub_test:
    nwb_output_path = data_path / "nwb_{subject_list[0]}_running_stub"
    nwb_final_output_path = data_path / f"nwb_{subject_list[0]}_stub"
else:
    nwb_output_path = data_path / f"nwb_{subject_list[0]}_running"
    nwb_final_output_path = data_path / f"nwb_{subject_list[0]}"
nwb_output_path.mkdir(exist_ok=True)
nwb_final_output_path.mkdir(exist_ok=True)


if stub_test:
    nwbfile_list = [nwb_output_path / f"{session.stem}_stub.nwb" for session in session_path_list]
else:
    nwbfile_list = [nwb_output_path / f"{session.stem}.nwb" for session in session_path_list]

global_metadata = load_dict_from_file(metadata_path)
subject_info_table = load_dict_from_file(subject_info_path)

for session_path, nwbfile_path in tqdm(zip(session_path_list, nwbfile_list), **progress_bar_options):
    simplefilter("ignore")
    conversion_options = dict()
    session_id = session_path.name

    xml_file_path = session_path / f"{session_id}.xml"
    raw_file_path = session_path / f"{session_id}.dat"
    lfp_file_path = session_path / f"{session_id}.lfp"

    aux_file_path = session_path / "auxiliary.dat"
    rhd_file_path = session_path / "info.rhd"
    sleep_mat_file_path = session_path / f"{session_id}.SleepState.states.mat"
    ripple_mat_file_paths = [x for x in session_path.iterdir() for suffix in x.suffixes if "ripples" in suffix.lower()]

    # I know I'll need this for other sessions, just not yet
    # if not raw_file_path.is_file() and (session_path / f"{session_id}.dat_orig").is_file:
    #     raw_file_path = session_path / f"{session_id}.dat_orig"

    # raw_file_path = session_path / f"{session_id}.dat" if (session_path / f"{session_id}.dat").is_file() else
    ecephys_start_time = get_session_datetime(session_id=session_id)
    ecephys_stop_time = ecephys_start_time + timedelta(
        seconds=NeuroscopeRecordingExtractor(file_path=lfp_file_path, xml_file_path=xml_file_path).get_num_frames()
        / 1250.0
    )
    source_data = dict(
        Glucose=dict(
            session_path=str(session_path),
            ecephys_start_time=str(ecephys_start_time),
            ecephys_stop_time=str(ecephys_stop_time),
        ),
        NeuroscopeLFP=dict(
            file_path=str(lfp_file_path),
            gain=conversion_factor,
            xml_file_path=str(xml_file_path),
            spikeextractors_backend=True,
        ),
    )

    if raw_file_path.is_file():
        source_data.update(
            NeuroscopeRecording=dict(
                file_path=str(raw_file_path),
                gain=conversion_factor,
                xml_file_path=str(xml_file_path),
                spikeextractors_backend=True,
            )
        )
        conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test))

    if aux_file_path.is_file() and rhd_file_path.is_file():
        source_data.update(Accelerometer=dict(dat_file_path=str(aux_file_path), rhd_file_path=str(rhd_file_path)))

    if sleep_mat_file_path.is_file():
        source_data.update(SleepStates=dict(mat_file_path=str(sleep_mat_file_path)))

    if any(ripple_mat_file_paths):
        source_data.update(Ripples=dict(mat_file_paths=ripple_mat_file_paths))

    converter = TingleyMetabolicConverter(source_data=source_data)
    metadata = converter.get_metadata()
    metadata = dict_deep_update(metadata, global_metadata)
    session_description = "Consult Supplementary Table 1 from the publication for more information about this session."
    metadata["NWBFile"].update(
        # session_description=subject_info_table.get(
        #     metadata["Subject"]["subject_id"],
        #     "Consult Supplementary Table 1 from the publication for more information about this session.",
        # ),
        # experiment_description=subject_info_table.get(
        #    metadata["Subject"]["subject_id"],
        #    "Consult Supplementary Table 1 from the publication for more information about this session.",
        # ),
        # Since no mapping of subject_ids to ST1, just leave this for all.
        session_description=session_description,
        experiment_description=session_description,
    )
    if metadata["Ecephys"]["Device"][0]["name"] == "Device_ecephys":
        del metadata["Ecephys"]["Device"][0]
    for electrode_group_metadata in metadata["Ecephys"]["ElectrodeGroup"]:
        electrode_group_metadata.update(device=metadata["Ecephys"]["Device"][0]["name"])

    ecephys_start_time_increment = (
        ecephys_start_time - converter.data_interface_objects["Glucose"].session_start_time
    ).total_seconds()
    conversion_options.update(
        NeuroscopeLFP=dict(
            stub_test=stub_test, starting_time=ecephys_start_time_increment, iterator_opts=dict(buffer_gb=buffer_gb)
        )
    )
    if raw_file_path.is_file():
        conversion_options.update(
            NeuroscopeRecording=dict(
                stub_test=stub_test,
                starting_time=ecephys_start_time_increment,
                es_key="ElectricalSeries_raw",
                iterator_opts=dict(buffer_gb=buffer_gb),
            )
        )
    if aux_file_path.is_file() and rhd_file_path.is_file():
        conversion_options.update(
            Accelerometer=dict(stub_test=stub_test, ecephys_start_time=ecephys_start_time_increment)
        )
    if sleep_mat_file_path.is_file():
        conversion_options.update(SleepStates=dict(ecephys_start_time=ecephys_start_time_increment))
    if any(ripple_mat_file_paths):
        conversion_options.update(Ripples=dict(stub_test=stub_test, ecephys_start_time=ecephys_start_time_increment))

    converter.run_conversion(
        nwbfile_path=str(nwbfile_path),
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
    nwbfile_path.rename(nwb_final_output_path / nwbfile_path.name)
    dandi_upload(dandiset_id=dandiset_id, nwb_folder_path=nwb_final_output_path)
