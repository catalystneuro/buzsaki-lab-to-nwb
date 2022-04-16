"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path

from buzsaki_lab_to_nwb import PeyracheNWBConverter

base_path = Path("D:/BuzsakiData/PeyracheA")
convert_sessions = [session for mouse in base_path.iterdir() if mouse.is_dir() for session in mouse.iterdir()]

experimenter = "Adrien Peyrache"
paper_descr = (
    "The data set contains recordings made from multiple anterior thalamic nuclei, mainly "
    "the antero-dorsal (AD) nucleus, and subicular areas, mainly the post-subiculum (PoS), in freely moving "
    "mice. Thalamic and subicular electrodes yielding high number of the so-called Head-Direction (HD) cells were "
    "likely to be located in the AD nucleus and the PoS, respectively. Electrode placement was confirmed by "
    "histology. The data was obtained during 42 recording sessions and includes responses of 720 neurons in the "
    "thalamus and 357 neurons in the PoS, in seven animals while they foraged for food in an open environment "
    "(53- x 46-cm).  Three animals were recorded simultaneously in the thalamus and the PoS (21 sessions). In the "
    "four other animals, electrodes were implanted in the anterior thalamus and in the pyramidal layer of the CA1 "
    "area of the hippocampus but only to record Local field Potentials (LFPs). The raw (broadband) data was recorded "
    "at 20KHz, simultaneously from 64 to 96 channels."
)
paper_info = (
    "Internally organized mechanisms of the head direction sense. "
    "Peyrache A, Lacroix MM, Petersen PC, Buzsaki G, Nature Neuroscience. 2015"
)

device_descr = (
    "Silicon probes (Neuronexus Inc. Ann Arbor, MI) were mounted on movable drives for recording "
    "of neuronal activity and local field potentials (LFP) in the anterior thalamus (n = 7 mice) and, in addition "
    "in the post-subiculum (n = 3 out of 7 mice). In the four animals implanted only in the anterior thalamus, "
    "electrodes were also implanted in the hippocampal CA1 pyramidal layer for accurate sleep scoring: three to six "
    "50 μm tungsten wires (Tungsten 99.95%, California Wire Company) were inserted in silicate tubes and attached to "
    "a micromanipulator. Thalamic probes were implanted in the left hemisphere, perpendicularly to the midline, "
    "(AP: –0.6 mm; ML:–0.5 to –1.9 mm; DV: 2.2 mm), with a 10 – 15° angle, the shanks pointing toward midline "
    "(see Supplementary Fig. 1a–f). Post-subicular probes were inserted at the following coordinates: AP: –4.25 mm: "
    "ML: –1 to –2 mm; DV: 0.75 mm (Supplementary Fig. 1g,h). Hippocampal wire bundles were implanted above "
    "CA1 (AP: –2.2 mm; –1 to –1.6 mm ML; 1 mm DV). The probes consisted of 4, 6 or 8 shanks "
    "(200-μm shank separation) and each shank had 8 (4 or 8 shank probes; Buz32 or Buz64 Neuronexus) or 10 "
    "recording (6-shank probes; Buz64s) sites (160 μm2 each site; 1–3 M impedance), staggered to provide a "
    "two-dimensional arrangement (20 μm vertical separation)."
)

stub_test = True
conversion_factor = 0.3815  # Ampliplex
overwrite = False

for session_path in convert_sessions:
    folder_path = str(session_path)
    session_id = session_path.name
    nwbfile_path = base_path / f"{session_id}_stub.nwb"

    if not nwbfile_path.is_file() or overwrite:
        print(f"Converting session {session_id}...")

        eeg_file_path = str((session_path / f"{session_id}.eeg"))
        raw_data_folder_path = session_path / "raw"

        source_data = dict(
            NeuroscopeSorting=dict(folder_path=folder_path, load_waveforms=True),
            NeuroscopeLFP=dict(file_path=eeg_file_path, gain=conversion_factor),
            PeyracheMisc=dict(folder_path=folder_path),
        )
        conversion_options = dict(
            NeuroscopeSorting=dict(stub_test=stub_test, write_waveforms=True), NeuroscopeLFP=dict(stub_test=stub_test)
        )
        if raw_data_folder_path.is_dir():
            folder_path = str(raw_data_folder_path)
            source_data.update(NeuroscopeRecording=dict(folder_path=folder_path, gain=conversion_factor))
            conversion_options.update(NeuroscopeRecording=dict(stub_test=stub_test))
        else:
            conversion_options["NeuroscopeSorting"].update(write_ecephys_metadata=True)

        peyrache_converter = PeyracheNWBConverter(source_data)
        metadata = peyrache_converter.get_metadata()

        # Specific info
        metadata["NWBFile"].update(
            experimenter=experimenter, session_description=paper_descr, related_publications=paper_info
        )
        metadata["Subject"].update(
            subject_id=session_path.parent.name,
        )
        metadata["Ecephys"]["Device"][0].update(description=device_descr)

        peyrache_converter.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            conversion_options=conversion_options,
            overwrite=overwrite,
        )
