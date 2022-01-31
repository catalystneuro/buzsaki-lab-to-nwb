"""Authors: Cody Baker and Ben Dichter."""
import pandas as pd
import numpy as np
from scipy.io import loadmat
from pathlib import Path
from lxml import etree as et
from datetime import datetime

from nwb_conversion_tools import NWBConverter
from nwb_conversion_tools import (
    NeuroscopeRecordingInterface,
    NeuroscopeSortingInterface,
)

from .yutalfpdatainterface import YutaLFPInterface, get_reference_elec
from .yutapositiondatainterface import YutaPositionInterface
from .yutabehaviordatainterface import YutaBehaviorInterface
from ..utils.neuroscope import get_clusters_single_shank, read_spike_clustering


def get_UnitFeatureCell_features(fpath_base, session_id, session_path, nshanks):
    """Load features from matlab file. Handle occasional mismatches."""
    cols_to_get = ("fineCellType", "region", "unitID", "unitIDshank", "shank")
    matin = loadmat(str(fpath_base / "DGProject/DG_all_6__UnitFeatureSummary_add.mat"), struct_as_record=False,)[
        "UnitFeatureCell"
    ][0][0]

    all_ids = []
    all_shanks = []
    for shankn in range(1, nshanks + 1):
        ids = np.unique(read_spike_clustering(session_path, shankn))
        ids = ids[~np.isin(ids, (0, 1))]
        all_ids.append(ids)
        all_shanks.append(np.ones(len(ids), dtype=int) * shankn)
    np.hstack(all_ids)
    np.hstack(all_shanks)
    clu_df = pd.DataFrame({"unitIDshank": np.hstack(all_ids), "shank": np.hstack(all_shanks)})

    this_file = matin.fname == session_id
    mat_df = pd.DataFrame({col: getattr(matin, col)[this_file].ravel() for col in cols_to_get})

    return pd.merge(clu_df, mat_df, how="left", on=("unitIDshank", "shank"))


class YutaNWBConverter(NWBConverter):
    """Primary conversion class for the SenzaiY dataset."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeSorting=NeuroscopeSortingInterface,
        YutaLFP=YutaLFPInterface,
        YutaPosition=YutaPositionInterface,
        YutaBehavior=YutaBehaviorInterface,
    )

    def get_metadata(self):
        session_path = Path(self.data_interface_objects["NeuroscopeSorting"].source_data["folder_path"])
        subject_path = session_path.parent
        session_id = session_path.stem
        mouse_number = session_id[-9:-7]

        subject_xls = subject_path / f"DGProject/YM{mouse_number} exp_sheet.xlsx"
        hilus_csv_path = subject_path / "DGProject/early_session_hilus_chans.csv"
        if "-" in session_id:
            b = False
        else:
            b = True

        session_start = datetime.strptime(session_id[-6:], "%y%m%d")

        if subject_xls.is_file():
            subject_df = pd.read_excel(subject_xls)
            subject_data = dict()
            for key in [
                "genotype",
                "DOB",
                "implantation",
                "Probe",
                "Surgery",
                "virus injection",
                "mouseID",
            ]:
                names = subject_df.iloc[:, 0]
                if key in names.values:
                    subject_data[key] = subject_df.iloc[np.argmax(names == key), 1]
            if isinstance(subject_data["DOB"], datetime):
                age = str(session_start - subject_data["DOB"])
            else:
                age = None
        else:
            age = "unknown"
            subject_data = dict()
            print(f"Warning: no subject file detected for session {session_path}!")

        xml_filepath = session_path / f"{session_id}.xml"
        root = et.parse(str(xml_filepath)).getroot()

        shank_channels = [
            [int(channel.text) for channel in group.find("channels")]
            for group in root.find("spikeDetection").find("channelGroups").findall("group")
        ]

        all_shank_channels = np.concatenate(shank_channels)
        all_shank_channels.sort()
        nshanks = len(shank_channels)
        lfp_channel = get_reference_elec(subject_xls, hilus_csv_path, session_start, session_id, b=b)

        celltype_dict = {
            0: "unknown",
            1: "granule cells (DG) or pyramidal cells (CA3)  (need to use region info. see below.)",
            2: "mossy cell",
            3: "narrow waveform cell",
            4: "optogenetically tagged SST cell",
            5: "wide waveform cell (narrower, exclude opto tagged SST cell)",
            6: "wide waveform cell (wider)",
            8: "positive waveform unit (non-bursty)",
            9: "positive waveform unit (bursty)",
            10: "positive negative waveform unit",
        }

        df_unit_features = get_UnitFeatureCell_features(subject_path, session_id, session_path, nshanks)

        # there are occasional mismatches between the matlab struct
        # and the neuroscope files regions: 3: 'CA3', 4: 'DG'
        celltype_names = []
        for celltype_id, region_id in zip(df_unit_features["fineCellType"].values, df_unit_features["region"].values):
            if celltype_id == 1:
                if region_id == 3:
                    celltype_names.append("pyramidal cell")
                elif region_id == 4:
                    celltype_names.append("granule cell")
                else:
                    raise Exception("unknown type")
            elif not np.isfinite(celltype_id):
                celltype_names.append("missing")
            else:
                celltype_names.append(celltype_dict[celltype_id])

        sorting_electrode_groups = []
        for shankn in range(len(shank_channels)):
            df = get_clusters_single_shank(session_path, shankn + 1)
            for _, _ in df.groupby("id"):
                sorting_electrode_groups.append(f"shank{str(shankn+1)}")

        metadata = super().get_metadata()
        metadata["NWBFile"].update(
            session_start_time=session_start.astimezone(),
            session_id=session_id,
            institution="NYU",
            lab="Buzsaki",
        )
        metadata.update(Subject=dict(subject_id=session_id[:-7], species="Mus musculus", age=age))
        if "genotype" in subject_data:
            metadata["Subject"].update(genotype=subject_data["genotype"])
        metadata["Ecephys"]["Electrodes"].append(
            dict(
                name="theta_reference",
                description="This electrode was used to calculate LFP canonical bands.",
                data=list(all_shank_channels == lfp_channel),
            )
        )
        metadata.update(
            UnitProperties=[
                dict(
                    name="cell_type",
                    description="Name of cell type.",
                    data=celltype_names,
                ),
                dict(
                    name="global_id",
                    description="Global id for cell for entire experiment.",
                    data=df_unit_features["unitID"].values,
                ),
                dict(
                    name="shank_id",
                    description="0-indexed id of cluster of shank.",
                    # - 2 b/c the get_UnitFeatureCell_features removes 0 and 1 IDs from each shank
                    data=[x - 2 for x in df_unit_features["unitIDshank"].values],
                ),
                dict(
                    name="electrode_group",
                    description="The electrode group that each spike unit came from.",
                    data=sorting_electrode_groups,
                ),
            ]
        )

        return metadata
