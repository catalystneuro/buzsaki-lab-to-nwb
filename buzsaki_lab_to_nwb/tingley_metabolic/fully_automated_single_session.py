"""Run entire conversion."""
import os
import traceback
from pathlib import Path
from datetime import timedelta
from warnings import simplefilter

from shutil import rmtree
from natsort import natsorted
from nwbinspector.tools import get_s3_urls_and_dandi_paths

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
hub_globus_endpoint_id = "2b9b4d14-82a8-11ec-9f34-ed182a728dff"
# hub_globus_endpoint_id = "3d82aa0a-bc1d-11ec-8f83-e31722b18688"
dandiset_id = "000233"

stub_test = False
conversion_factor = 0.195  # Intany
buffer_gb = 50

data_path = Path("/shared/catalystneuro/TingleyD/")
home_path = Path("/home/jovyan/")

# data_path = Path("C:/Users/Raven/Documents/TingleyD/")


base_buzsaki_path = Path("/TingleyD/Tingley2021_ripple_glucose_paper/")
subject_id = "CGM37"
all_content = get_globus_dataset_content_sizes(
    globus_endpoint_id=buzsaki_globus_endpoint_id, path=(base_buzsaki_path / subject_id).as_posix()
)
dandi_content = list(get_s3_urls_and_dandi_paths(dandiset_id=dandiset_id).values())
dandi_session_datetimes = [
    "_".join(x.split("/")[1].split("_")[1].split("-")[-2:]) for x in dandi_content
]  # probably a better way to do this, just brute forcing for now
sessions = natsorted(list(set([Path(x).parent.name for x in all_content])))


session_idxs = set(range(len(sessions)))
for session_idx in session_idxs:
    assert os.environ.get("DANDI_API_KEY"), "Set your DANDI_API_KEY!"
    try:
        session_id = sessions[session_idx]
        # assert f"{session_id}/{session_id}.lfp" in all_content, "Skip session_idx {session_idx} - bad session!"
        if f"{session_id}/{session_id}.lfp" not in all_content:
            print(f"\nSkipping session_id {session_id} because there was no LFP (and hence likely a bad session). ")
            continue
        if any([x in session_id for x in dandi_session_datetimes]):
            print(f"\nSkipping session_id {session_id} because it is already on DANDI.")
            continue

        content_to_attempt_transfer = [
            f"{session_id}/{session_id}.xml",
            f"{session_id}/{session_id}.dat",
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
        total_time = estimate_total_conversion_runtime(total_mb=content_to_transfer_size / 1e6, transfer_rate_mb=3.0)
        total_cost = estimate_s3_conversion_cost(total_mb=content_to_transfer_size / 1e6, transfer_rate_mb=3.0)
        print(f"Total cost of {session_id}: ${total_cost}, total time: {total_time / 3600} hr")

        metadata_path = Path(__file__).parent / "tingley_metabolic_metadata.yml"
        subject_info_path = Path(__file__).parent / "tingley_metabolic_subject_info.yml"

        nwb_output_path = data_path / f"nwb_{session_id}"
        nwb_output_path.mkdir(exist_ok=True)
        nwbfile_path = nwb_output_path / f"{session_id}.nwb"
        session_path = data_path / f"{session_id}"
        session_path.mkdir(exist_ok=True)

        transfer_globus_content(
            source_endpoint_id=buzsaki_globus_endpoint_id,
            source_files=[
                [base_buzsaki_path / subject_id / x for x in content_to_transfer if ".csv" in x],
                [base_buzsaki_path / subject_id / x for x in content_to_transfer if ".csv" not in x],
            ],
            destination_endpoint_id=hub_globus_endpoint_id,
            destination_folder=session_path,
            progress_update_rate=30.0,
            progress_update_timeout=total_time * 10,
        )

        global_metadata = load_dict_from_file(metadata_path)
        subject_info_table = load_dict_from_file(subject_info_path)

        simplefilter("ignore")
        conversion_options = dict()

        xml_file_path = session_path / f"{session_id}.xml"
        raw_file_path = session_path / f"{session_id}.dat"
        lfp_file_path = session_path / f"{session_id}.lfp"

        aux_file_path = session_path / "auxiliary.dat"
        rhd_file_path = session_path / "info.rhd"
        sleep_mat_file_path = session_path / f"{session_id}.SleepState.states.mat"
        ripple_mat_file_paths = [
            x for x in session_path.iterdir() for suffix in x.suffixes if "ripples" in suffix.lower()
        ]

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

        if aux_file_path.is_file() and rhd_file_path.is_file():
            source_data.update(Accelerometer=dict(dat_file_path=str(aux_file_path), rhd_file_path=str(rhd_file_path)))

        if sleep_mat_file_path.is_file():
            source_data.update(SleepStates=dict(mat_file_path=str(sleep_mat_file_path)))

        if any(ripple_mat_file_paths):
            source_data.update(Ripples=dict(mat_file_paths=ripple_mat_file_paths))

        converter = TingleyMetabolicConverter(source_data=source_data)
        metadata = converter.get_metadata()
        metadata = dict_deep_update(metadata, global_metadata)
        session_description = (
            "Consult Supplementary Table 1 from the publication for more information about this session."
        )
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
                stub_test=stub_test,
                starting_time=ecephys_start_time_increment,
                iterator_opts=dict(buffer_gb=buffer_gb, display_progress=True),
            )
        )
        if raw_file_path.is_file():
            conversion_options.update(
                NeuroscopeRecording=dict(
                    stub_test=stub_test,
                    starting_time=ecephys_start_time_increment,
                    es_key="ElectricalSeries_raw",
                    iterator_opts=dict(buffer_gb=buffer_gb, display_progress=True),
                )
            )
        if aux_file_path.is_file() and rhd_file_path.is_file():
            conversion_options.update(
                Accelerometer=dict(stub_test=stub_test, ecephys_start_time=ecephys_start_time_increment)
            )
        if sleep_mat_file_path.is_file():
            conversion_options.update(SleepStates=dict(ecephys_start_time=ecephys_start_time_increment))
        if any(ripple_mat_file_paths):
            conversion_options.update(
                Ripples=dict(stub_test=stub_test, ecephys_start_time=ecephys_start_time_increment)
            )

        converter.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            conversion_options=conversion_options,
            overwrite=True,
        )
        try:
            rmtree(session_path)
        except OSError:
            if len(list(session_path.iterdir())) > 0:
                print(f"shutil.rmtree failed to clean directory for session {session_id}")
    except Exception as ex:
        # Clean up data files in event of any error
        try:
            rmtree(session_path, ignore_errors=True)
            rmtree(nwb_output_path, ignore_errors=True)
            rmtree(nwb_output_path.parent / dandiset_id, ignore_errors=True)
        except Exception:
            a = 1
    assert False, "Ending session."
