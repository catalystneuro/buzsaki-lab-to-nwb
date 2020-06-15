function nwb = add_ophys(nwb, roi_response_data, roi_image_masks, device_name, indicator, frame_rate, varargin)

p = inputParser;
p.KeepUnmatched = true;
p.PartialMatching = false;
p.StructExpand = false;

addParameter(p, 'frame_times', []);
addParameter(p, 'name_of_imaging_plane', 'ImagingPlane');
parse(p, varargin{:});

frame_times = p.Results.frame_times;
imaging_plane_name = p.Results.name_of_imaging_plane;


n_rois = size(roi_image_masks, 1);

optical_channel_varargin = pull_varargin(varargin, 'optical_channel');
optical_channel = types.core.OpticalChannel(optical_channel_varargin{:});

nwb.general_devices.set(device_name, types.core.Device());

imaging_plane_varargin = pull_varargin(varargin, 'imaging_plane');
imaging_plane = types.core.ImagingPlane( ...
    'indicator', indicator, ...
    'optial_channel', optical_channel, ...
    'imaging_rate', frame_rate, ...
    'device', types.untyped.SoftLink(['/general/devices/' device_name]), ...
    imaging_plane_varargin{:});

nwb.general_optophysiology.set(imaging_plane_name, imaging_plane);

imaging_plane_path = ['/general/optophysiology/' imaging_plane_name];

ophys_module = types.core.ProcessingModule(...
    'description', 'holds processed calcium imaging data');

plane_segmentation_varargin = pull_varargin(varargin, 'plane_segmentation');
plane_segmentation = types.core.PlaneSegmentation( ...
    'imaging_plane', imaging_plane, ...
    'colnames', {'imaging_mask'}, ...
    'id', types.core.ElementIdentifiers('data', int64(0:n_rois-1)), ...
    plane_segmentation_varargin{:});

plane_segmentation.image_mask = types.core.VectorData( ...
    'data', roi_image_masks, 'description', 'image masks');

img_seg = types.core.ImageSegmentation();
img_seg.planesegmentation.set('PlaneSegmentation', plane_segmentation)

ophys_module.nwbdatainterface.set('ImageSegmentation', img_seg);
nwb.processing.set('ophys', ophys_module);

plane_seg_object_view = types.untyped.ObjectView( ...
    '/processing/ophys/ImageSegmentation/PlaneSegmentation');

roi_table_region = types.core.DynamicTableRegion( ...
    'table', plane_seg_object_view, ...
    'description', 'all_rois', ...
    'data', [0 n_rois-1]');

roi_response_series_varargin = pull_varargin(varargin, 'roi_response_series');

if frame_times
    roi_response_series = types.core.RoiResponseSeries( ...
    'rois', roi_table_region, ...
    'data', roi_response_data, ...
    'data_unit', 'lumens', ...
    'timestamps', frame_times, ...
    roi_response_series_varargin{:});
else
    roi_response_series = types.core.RoiResponseSeries( ...
    'rois', roi_table_region, ...
    'data', roi_response_data, ...
    'data_unit', 'lumens', ...
    'starting_time_rate', frame_rate, ...
    roi_response_series_varargin{:});

end

fluorescence = types.core.Fluorescence();
fluorescence.roiresponseseries.set('RoiResponseSeries', roi_response_series);

ophys_module.nwbdatainterface.set('Fluorescence', fluorescence);

nwb.processing.set('ophys', ophys_module);







end