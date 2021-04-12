"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

from buzsaki_lab_to_nwb import FujisawaNWBConverter

# Note that this conversion required heavy rework of the data folder structure 

base_path = Path("D:/BuzsakiData/FujisawaS")
convert_sessions = [
    subsession for mouse in base_path.iterdir() if mouse.is_dir()
    for session in mouse.iterdir() for subsession in session.iterdir()
]

experimenter = "Shigeyoshi Fujisawa"
paper_descr = (
    "Although short-term plasticity is believed to play a fundamental role in cortical computation, empirical evidence "
    "bearing on its role during behavior is scarce. Here we looked for the signature of short-term plasticity in the "
    "fine-timescale spiking relationships of a simultaneously recorded population of physiologically identified "
    "pyramidal cells and interneurons, in the medial prefrontal cortex of the rat, in a working memory task. On "
    "broader timescales, sequentially organized and transiently active neurons reliably differentiated between "
    "different trajectories of the rat in the maze. On finer timescales, putative monosynaptic interactions reflected "
    "short-term plasticity in their dynamic and predictable modulation across various aspects of the task, beyond a "
    "statistical accounting for the effect of the neurons' co-varying firing rates. Seeking potential mechanisms for "
    "such effects, we found evidence for both firing pattern-dependent facilitation and depression, as well as for a "
    "supralinear effect of presynaptic coincidence on the firing of postsynaptic targets."
)
paper_info = [
    "Behavior-dependent short-term assembly dynamics in the medial prefrontal cortex."
    "Fujisawa S, Amarasingham A, Harrison M, Buzsáki G, Nature Neuroscience. 2008"
]

device_descr = (
    "Rats were implanted with silicon probes in the prefrontal cortex, layer 2/3 or layer 5 "
    "(anteroposterior = 3.0–4.4 mm, medio-lateral = 0.5 mm). The recording silicon probe was attached to a "
    "micromanipulator and moved gradually to its desired depth position. The probe consisted of eight shanks "
    "(200-μm shank separation) and each shank had eight recording sites (160 μm2 each site; 1–3 MΩ impedance), "
    "staggered to provide a two-dimensional arrangement (20-μm vertical separation)."
)

stub_test = True
conversion_factor = 0.3815  # Ampliplex

for session_path in convert_sessions:
    folder_path = str(session_path)
    subject_name = session_path.parent.parent.name
    session_id = session_path.name
    print(f"Converting session {session_id}...")

    lfp_file_path = str(session_path / f"{session_id}.eeg")
    raw_data_folder_path = lfp_file_path.replace("eeg", "dat")

    source_data = dict(NeuroscopeLFP=dict(file_path=lfp_file_path, gain=conversion_factor))
    conversion_options = dict(NeuroscopeLFP=dict(stub_test=stub_test))
    if any([x for x in session_path.iterdir() if ".clu" in x.suffixes]):
        source_data.update(NeuroscopeSorting=dict(folder_path=folder_path))
        conversion_options.update(NeuroscopeSorting=dict(stub_test=stub_test))
    if Path(raw_data_folder_path).is_file():
        source_data.update(NeuroscopeRecording=dict(folder_path=folder_path, gain=conversion_factor))
        conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test))

    converter = FujisawaNWBConverter(source_data)
    metadata = converter.get_metadata()

    # Specific info
    metadata['NWBFile'].update(
        experimenter=experimenter,
        session_description=paper_descr,
        related_publications=paper_info
    )
    metadata['Ecephys']['Device'][0].update(description=device_descr)

    nwbfile_path = str(base_path / f"{session_id}_stub.nwb")
    converter.run_conversion(
        nwbfile_path=nwbfile_path,
        metadata=metadata,
        conversion_options=conversion_options,
        overwrite=True
    )
