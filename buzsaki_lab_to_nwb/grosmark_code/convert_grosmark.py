"""Authors: Cody Baker and Ben Dichter."""
from buzsaki_lab_to_nwb import GrosmarkNWBConverter
from pathlib import Path
import os

base_path = Path("D:/BuzsakiData/GrosmarkAD")
mice_names = ["Achilles", "Buddy", "Cicero", "Gatsby"]

convert_sessions = [session for mouse_name in mice_names for session in (base_path / Path(mouse_name)).iterdir()]

experimenter = "Andres Grosmark"
paper_descr = "This data set is composed of eight bilateral silicon-probe multi-cellular electrophysiological "
"recordings performed on four male Long-Evans rats in the Buzsáki lab at NYU. These recordings were "
"performed to assess the effect of novel spatial learning on hippocampal CA1 neural firing and LFP "
"patterns in naïve animals. Each session consisted of a long (~4 hour) PRE rest/sleep epoch home-cage "
"recordings performed in a familiar room, followed by a Novel MAZE running epoch (~45 minutes) in which "
"the animals were transferred to a novel room, and water-rewarded to run on a novel maze. These mazes "
"were either A) a wooden 1.6m linear platform, B) a wooden 1m diameter circular platform or C) a 2m "
"metal linear platform. Animals were rewarded either at both ends of the linear platform, or at a "
"predetermined location on the circular platform. The animal was gently encouraged to run "
"unidirectionally on the circular platform. After the MAZE epochs the animals were transferred back "
"to their home-cage in the familiar room where a long (~4 hour) POST rest/sleep was recorded. All eight "
"sessions were concatenated from the PRE, MAZE, and POST recording epochs. In addition to hippocampal "
"electrophysiological recordings, neck EMG and head-mounted accelerometer signals were recorded, and the "
"animal’s position during MAZE running epochs was tracked via head-mounted LEDs."
paper_info = [
    "Grosmark, A.D., and Buzsáki, G. (2016). "
    "Diversity in neural firing dynamics supports both rigid and learned hippocampal sequences. "
    "Science 351, 1440–1443.",
    "Chen, Z., Grosmark, A.D., Penagos, H., and Wilson, M.A. (2016). "
    "Uncovering representations of sleep-associated hippocampal ensemble spike activity. "
    "Sci. Rep. 6, 32193.",
]

device_descr = "Silicon probe electrodes; all probes were implanted parallel to the "
"septo-temporal axis of the dorsal hippocampus. First eight shanks pertain to CA1 left hemisphere, "
"second eight pertain to CA1 right hemisphere."
bad_electrodes = dict(
    Buddy_06272013=[24, 27, 58],
    Gatsby_08022013=[],
    Gatsby_08282013=[35, 45, 47],
    Achilles_10252013=[],
    Achilles_11012013=[],
    Cicero_09012014=[],
    Cicero_091020114=[],
    Cicero_09172014=[],
)

for session_path in convert_sessions:
    folder_path = session_path.absolute()
    session_id = session_path.name
    print(f"Converting session {session_id}...")

    input_args = dict(
        NeuroscopeSorting=dict(folder_path=folder_path, keep_mua_units=False),
        GrosmarkLFP=dict(folder_path=folder_path),
        GrosmarkBehavior=dict(folder_path=folder_path),
    )

    grosmark_converter = GrosmarkNWBConverter(**input_args)
    metadata = grosmark_converter.get_metadata()

    # Specific info
    metadata["NWBFile"].update(
        experimenter=experimenter,
        session_description=paper_descr,
        related_publications=paper_info,
    )

    metadata["Subject"].update(
        species="Rattus norvegicus domestica - Long Evans",
        genotype="Wild type",
        sex="male",
        weight="250-350g",
    )
    # No age information reported in either publication, not available on dataset or site

    f"see {session_id}.xml or {session_id}.sessionInfo.mat for more information"
    metadata[grosmark_converter.get_recording_type()]["Ecephys"]["Device"][0].update(description=device_descr)
    metadata[grosmark_converter.get_recording_type()]["Ecephys"]["Electrodes"].append(
        dict(
            name="bad_electrode",
            description="Indicator for if the electrode was removed from analysis due to "
            "low-amplitude or instabilities.",
            data=[
                x in bad_electrodes[session_id]
                for x in range(len(metadata[grosmark_converter.get_recording_type()]["Ecephys"]["subset_channels"]))
            ],
        )
    )

    nwbfile_path = os.path.join(folder_path, f"{session_id}_stub.nwb")
    grosmark_converter.run_conversion(nwbfile_path=nwbfile_path, metadata_dict=metadata, stub_test=True)
