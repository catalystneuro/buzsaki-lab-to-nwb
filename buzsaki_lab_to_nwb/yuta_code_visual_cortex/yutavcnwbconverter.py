"""Authors: Heberto Mayorquin and Cody Baker."""
import dateutil
from pathlib import Path
from datetime import datetime

from nwb_conversion_tools import NWBConverter, NeuroscopeRecordingInterface, NeuroscopeLFPInterface, PhySortingInterface

from .yutavcbehaviorinterface import YutaVCBehaviorInterface
from .yuta_vc_utils import read_matlab_file


class YutaVCNWBConverter(NWBConverter):
    """Primary conversion class for the SenzaiY visual cortex data set."""

    data_interface_classes = dict(
        NeuroscopeRecording=NeuroscopeRecordingInterface,
        NeuroscopeLFP=NeuroscopeLFPInterface,
        YutaVCBehavior=YutaVCBehaviorInterface,
        PhySorting=PhySortingInterface,
    )

    def __init__(self, source_data: dict):
        super().__init__(source_data=source_data)

        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
        session_path = lfp_file_path.parent
        session_id = session_path.stem

        # Electrode locations
        electrode_chan_map_file_path = session_path / "chanMap.mat"
        chan_map = read_matlab_file(file_path=electrode_chan_map_file_path)
        xcoords = [x[0] for x in chan_map["xcoords"]]
        ycoords = [y[0] for y in chan_map["ycoords"]]
        for channel_id in chan_map["chanMap0ind"]:
            self.data_interface_objects["NeuroscopeLFP"].recording_extractor.set_channel_locations(
                locations=[xcoords[channel_id], ycoords[channel_id]], channel_ids=channel_id
            )
            if "NeuroscopeRecording" in self.data_interface_objects:
                self.data_interface_objects["NeuroscopeRecording"].recording_extractor.set_channel_locations(
                    locations=[xcoords[channel_id], ycoords[channel_id]], channel_ids=channel_id
                )

        # Custom unit properties - should be a part of CellExplorerInterface, but this version is unsupported
        n_units = len(self.data_interface_objects["PhySorting"].sorting_extractor.get_unit_ids())
        cell_matrics_file_path = session_path / f"{session_id}.cell_metrics.cellinfo.mat"
        cell_metrics = read_matlab_file(file_path=cell_matrics_file_path)["cell_metrics"]
        cell_metrics_map = dict(
            maxWaveformCh="max_channel",
            peakVoltage="peak_voltage",
            throughToPeak="peak_to_valley",
            thetaModulationIndex="theta_modulation_index",
            synapticEffect="synaptic_effect",
            putativeCellType="cell_type",
            refractoryPeriodViolation="refractory_period_violation",
            populationModIndex="population_mod_index",
            polarity="polarity",
            firingRate="firing_rate",
            cv2="coefficient_of_variation",
            brainRegion="brain_region",
            ab_ratio="ab_ratio",
        )
        for property_key, property_name in cell_metrics_map.items():
            try:
                if property_key in ["synapticEffect", "putativeCellType", "brainRegion"]:
                    values = [str(x[0]) for x in cell_metrics[property_key][0][0][0]]
                else:
                    values = cell_metrics[property_key][0][0][0]
                if len(values) != n_units:
                    print(f"Skipping unit property {property_name} in session {session_id} due to length mismatch!")
                else:
                    self.data_interface_objects["PhySorting"].sorting_extractor.set_units_property(
                        property_name=property_name, values=values
                    )
            except ValueError:  # only safe way I know of to check key existence in numpy void object
                print(f"Skipping unit property {property_name} in session {session_id} due to missing key!")

    # def get_metadata_schema(self):
    #     metadata_schema = super().get_metadata_schema()
    #     metadata_schema["properties"]["Ecephys"]["properties"].update(
    #         ElectricalSeries_raw=get_schema_from_hdmf_class(ElectricalSeries),
    #         ElectricalSeries_processed=get_schema_from_hdmf_class(ElectricalSeries),
    #     )
    #     return metadata_schema

    def get_metadata(self):
        lfp_file_path = Path(self.data_interface_objects["NeuroscopeLFP"].source_data["file_path"])
        session_id = lfp_file_path.stem

        subject_id, datetime_string = str(lfp_file_path.stem).split("_")
        session_start = datetime.strptime(datetime_string, "%y%m%d")
        session_start = session_start.astimezone(tz=dateutil.tz.gettz("US/Eastern")).isoformat()

        metadata = super().get_metadata()
        metadata["NWBFile"].update(session_start_time=session_start, session_id=session_id)
        metadata.update(Subject=dict(subject_id=subject_id))
        return metadata
