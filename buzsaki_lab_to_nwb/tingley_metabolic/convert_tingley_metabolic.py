"""Run entire conversion."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from tqdm import tqdm
from nwb_conversion_tools.utils.json_schema import load_dict_from_file
from nwb_conversion_tools.utils.json_schema import dict_deep_update

from buzsaki_lab_to_nwb.tingley_metabolic import (
    TingleyMetabolicConverter,
    load_subject_glucose_series,
    get_subject_ecephys_session_start_times,
)

n_jobs = 20
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


session_path_list = [subject_path.iterdir() for subject_path in (data_path / "metadata_metabolic.yml").iterdir()]
if stub_test:
    nwbfile_list = [nwb_output_path / f"{session.parent.stem}_{session.stem}_stub.nwb" for session in session_path_list]
else:
    nwbfile_list = [nwb_output_path / f"{session.parent.stem}_{session.stem}.nwb" for session in session_path_list]

global_metadata = load_dict_from_file(metadata_path)
subject_info_table = load_dict_from_file(subject_info_path)


def convert_session(session_path, nwbfile_path):
    """Run coonversion."""
    print("----------------")
    print(session_path)
    print(nwbfile_path)

    session_id = session_path.name
    lfp_file_path = session_path / f"{session_path.name}.lfp"
    raw_file_path = session_path / f"{session_id}.dat"
    aux_file_path = session_path / "auxiliary.dat"
    rhd_file_path = session_path / f"{session_id}.rhd"
    xml_file_path = session_path / f"{session_id}.xml"

    subject_id = session_id.split("_")[0]
    subject_glucose_data = load_subject_glucose_series(session_path=session_path)
    subject_ecephys_session_start_times = get_subject_ecephys_session_start_times(session_path=session_path)
    # segment the ecephys against the glucose, return sub-series of glucose
    # if sub-series is non-empty, include GlucoseInterface(series=sub_series)
    #     and increment the starting_times of .dat and .lfp interfaces
    # else do not include glucose and just write ecephys with default start times

    print("raw file available...", raw_file_path.is_file())
    print("lfp file available...", lfp_file_path.is_file())
    source_data = dict()
    conversion_options = dict()

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

    converter = TingleyMetabolicConverter(source_data=source_data)

    metadata = converter.get_metadata()
    metadata = dict_deep_update(metadata, global_metadata)
    metadata["NWBFile"].update(
        session_description=subject_info_table.get(
            metadata["NWBFile"]["Subject"]["subject_id"],
            "Consult Supplementary Table 1 from the publication for more information about this session.",
        )
    )

    converter.run_conversion(
        nwbfile_path=str(nwbfile_path),
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True,
    )
    print("Done with conversion!")


with ProcessPoolExecutor(max_workers=n_jobs) as executor:
    futures = []
    for session_path, nwbfile_path in zip(session_path_list, nwbfile_list):
        futures.append(executor.submit(convert_session, session_path=session_path, nwbfile_path=nwbfile_path))
    completed_futures = tqdm(as_completed(futures), desc="Running conversion...", position=0, leave=False)
    for future in completed_futures:
        pass
