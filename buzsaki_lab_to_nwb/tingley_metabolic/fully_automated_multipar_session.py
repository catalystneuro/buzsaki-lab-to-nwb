"""Run entire conversion."""
import os
import json
from pathlib import Path
from datetime import timedelta
from warnings import simplefilter
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

from shutil import rmtree
from natsort import natsorted
from nwbinspector.tools import get_s3_urls_and_dandi_paths

from nwb_conversion_tools.tools.data_transfers import (
    automatic_dandi_upload,
    estimate_total_conversion_runtime,
    estimate_s3_conversion_cost,
    get_globus_dataset_content_sizes,
    transfer_globus_content,
)
from nwb_conversion_tools.utils import load_dict_from_file, dict_deep_update
from spikeextractors import NeuroscopeRecordingExtractor

from buzsaki_lab_to_nwb.tingley_metabolic import TingleyMetabolicConverter, get_session_datetime

assert os.environ.get("DANDI_API_KEY"), "Set your DANDI_API_KEY!"

buzsaki_globus_endpoint_id = "188a6110-96db-11eb-b7a9-f57b2d55370d"
hub_globus_endpoint_id = "2b9b4d14-82a8-11ec-9f34-ed182a728dff"
dandiset_id = "000233"

stub_test = False
conversion_factor = 0.195  # Intan
buffer_gb = 3
n_jobs = 3
data_size_threshold = 5 * 1e9  # GB

data_path = Path("/shared/catalystneuro/TingleyD/")
home_path = Path("/home/jovyan/")


base_buzsaki_path = Path("/TingleyD/Tingley2021_ripple_glucose_paper/")
subject_ids = iter(
    ["CGM58", "CGM60", "A63", "Bruce", "DT12", "dt15", "flex1", "ros", "Vanessa"]
)  # 47 and 50 have malformed csv?


def _transfer_and_convert(subject_id):
    try:
        content_cache_file_path = Path(f"/shared/catalystneuro/TingleyD/cache/cache_content_{subject_id}")
        if not content_cache_file_path.exists():
            all_content = get_globus_dataset_content_sizes(
                globus_endpoint_id=buzsaki_globus_endpoint_id, path=(base_buzsaki_path / subject_id).as_posix()
            )
            with open(content_cache_file_path, mode="w") as fp:
                json.dump(all_content, fp)
        else:
            with open(content_cache_file_path, mode="r") as fp:
                all_content = json.load(fp)
        dandi_content = list(get_s3_urls_and_dandi_paths(dandiset_id=dandiset_id).values())
        dandi_session_datetimes = [
            "_".join(x.split("/")[1].split("_")[-3:-1]) for x in dandi_content
        ]  # probably a better way to do this, just brute forcing for now
        sessions = set([Path(x).parent.name for x in all_content]) - set([""])  # "" for .csv
        unconverted_sessions = natsorted(
            [
                session_id
                for session_id in sessions
                if "_".join(session_id.split("_")[-2:]) not in dandi_session_datetimes
            ]
        )  # natsorted for consistency on each run

        gen = iter(unconverted_sessions)
        session_id = next(gen)
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
        j = 0
        stop = False
        while (
            f"{session_id}/{session_id}.lfp" not in all_content or content_to_transfer_size > data_size_threshold
        ) and j <= len(unconverted_sessions):
            j += 1
            try:
                session_id = next(gen)
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
            except StopIteration:
                try:
                    subject_id = next(subject_ids)
                    content_cache_file_path = Path(f"/shared/catalystneuro/TingleyD/cache/cache_content_{subject_id}")
                    if not content_cache_file_path.exists():
                        all_content = get_globus_dataset_content_sizes(
                            globus_endpoint_id=buzsaki_globus_endpoint_id,
                            path=(base_buzsaki_path / subject_id).as_posix(),
                        )
                        with open(content_cache_file_path, mode="w") as fp:
                            json.dump(all_content, fp)
                    else:
                        with open(content_cache_file_path, mode="r") as fp:
                            all_content = json.load(fp)
                    dandi_content = list(get_s3_urls_and_dandi_paths(dandiset_id=dandiset_id).values())
                    dandi_session_datetimes = [
                        "_".join(x.split("/")[1].split("_")[-3:-1]) for x in dandi_content
                    ]  # probably a better way to do this, just brute forcing for now
                    sessions = set([Path(x).parent.name for x in all_content]) - set([""])  # "" for .csv
                    unconverted_sessions = natsorted(
                        [
                            session_id
                            for session_id in sessions
                            if "_".join(session_id.split("_")[-2:]) not in dandi_session_datetimes
                        ]
                    )  # natsorted for consistency on each run
                    j = 0
                except StopIteration:
                    stop = True
                    print("\nAll remaining sessions missing LFP or too large.")
        if j == len(unconverted_sessions) or stop:
            assert False

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
            progress_update_rate=total_time / 20,  # every 5% or so
            progress_update_timeout=max(total_time * 2, 5 * 60),
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
        return True, session_path, nwb_output_path
    except Exception:
        return False, False, False


def _transfer_convert_and_upload(subject_id):
    try:
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_transfer_and_convert, subject_id=subject_id)
        success, session_path, nwb_folder_path = future.result()
        if success:
            try:
                rmtree(session_path, ignore_errors=True)
                automatic_dandi_upload(dandiset_id=dandiset_id, nwb_folder_path=nwb_folder_path)
            finally:
                rmtree(nwb_folder_path, ignore_errors=True)
                rmtree(nwb_folder_path.parent / dandiset_id, ignore_errors=True)
    finally:  # try to cleanup again
        rmtree(session_path, ignore_errors=True)
        rmtree(nwb_folder_path, ignore_errors=True)
        rmtree(nwb_folder_path.parent / dandiset_id, ignore_errors=True)


futures = []
n_jobs = None if n_jobs == -1 else n_jobs  # concurrents uses None instead of -1 for 'auto' mode
with ProcessPoolExecutor(max_workers=n_jobs) as executor:
    for subject_id in subject_ids:
        futures.append(executor.submit(_transfer_convert_and_upload, subject_id=subject_id))
nwbfiles_iterable = tqdm(as_completed(futures), desc="Converting subjects...")
for future in nwbfiles_iterable:
    _ = future.result()
