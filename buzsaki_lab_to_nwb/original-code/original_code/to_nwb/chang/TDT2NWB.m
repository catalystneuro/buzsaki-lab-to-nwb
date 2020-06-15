blockpath = '/Users/bendichter/Desktop/Chang/data/TDTBackup/EC125_B22';
imaging_path = '/Users/bendichter/Desktop/Chang/data/EC125/Imaging';
elecspath = fullfile(imaging_path, 'elecs', 'TDT_elecs_all.mat');
hilb_hg_path = '/Users/bendichter/Desktop/Chang/data/EC125/EC125_B22/HilbAA_70to150_8band';

[basepath, blockname] = fileparts(blockpath);

nwb_path = fullfile(basepath, [blockname '.nwb']);
%%
tdt = contrib.tdt.TDTbin2mat(blockpath);

%%
date = datevec([tdt.info.date tdt.info.utcStartTime]);

session_start_time = datetime(date,'Format','yyyy-MM-dd''T''HH:mm:SSZZ',...
    'TimeZone','local');

file = nwbfile('session_description', 'a test NWB File', ...
    'identifier', blockname, ...
    'session_start_time', session_start_time);
%% Electrode Table

[file, ecog_channels] = elecs2ElectrodeTable(file, elecspath);

x = length(file.general_extracellular_ephys_electrodes.id.data);

ov = types.untyped.ObjectView('/general/extracellular_ephys/electrodes');

electrode_table_region = types.core.DynamicTableRegion('table', ov, ...
    'description', 'all electrodes',...
    'data', [1 x]');

%% ECoG

stream_names = fieldnames(tdt.streams);

ecog_stream_names = sort(stream_names(contains(stream_names, 'Wav')));

Data = [];
for i = 1:length(ecog_stream_names)
    stream = tdt.streams.(ecog_stream_names{i});
    Data = [Data, stream.data'];
end
Data = Data(:, ecog_channels);

es = types.core.ElectricalSeries('starting_time', stream.startTime,...
    'starting_time_rate', stream.fs,...
    'data',Data',...
    'electrodes', electrode_table_region,...
    'data_unit', 'V');

file.acquisition.set('ECoG', es);


ECoG_soft_link = types.untyped.SoftLink('/aquisition/ECoG');


%% ANIN

stream = tdt.streams.ANIN;

labels = {'microphone', 'speaker1', 'speaker2', 'anin4'};

for i = 1:length(labels)
    ts = types.core.TimeSeries('starting_time',stream.startTime,...
        'starting_time_rate',stream.fs,...
        'data',stream.data(i,:)',...
        'data_unit','V?');
    file.acquisition.set(labels{i}, ts);
end

%% Cortical Surface
% generateExtension('/Users/bendichter/dev/nwbext_ecog/nwbext_ecog/ecog.namespace.yaml');

mesh_dir = fullfile(imaging_path, 'Meshes');
mesh_file_list = dir([mesh_dir '/*_pial.mat']);
mesh_file_list = {mesh_file_list.name};

cortical_surfaces = types.ecog.CorticalSurfaces;

for i = 1:length(mesh_file_list)
    mesh_file = mesh_file_list{i};
    surf_load = load(fullfile(mesh_dir, mesh_file));
    if isfield(surf_load,'mesh')
        faces = surf_load.mesh.tri - 1; % faces stored as 0-indexed in nwbext_ecog
        vertices = surf_load.mesh.vert;
    elseif isfield(surf_load,'cortex')
        faces = surf_load.cortex.tri - 1; % faces stored as 0-indexed in nwbext_ecog
        vertices = surf_load.cortex.vert;
    else
        keyboard
    end
    surf = types.ecog.Surface('faces', faces', 'vertices', vertices');
    surf_name = mesh_file(find(mesh_file == '_', 1)+1 : end-9);
    cortical_surfaces.surface.set(surf_name, surf);
end

file.acquisition.set('CorticalSurfaces', cortical_surfaces);


%% Hilbert AA
% generateExtension('/Users/bendichter/dev/to_nwb/to_nwb/extensions/time_frequency/time_frequency.namespace.yaml');
hilbert = types.core.ProcessingModule('description', 'ecephys module');
    
%%

data = readhtks(hilb_hg_path,[],[],1);

data = permute(data,[2,3,1]);

filter_centers = [70.66172888, 78.01687387,  86.13761233, 95.1036345 , ...
    105.00292557, 115.93262903, 128., 141.32345775];
filter_sigmas = [3.43753263, 3.61201023, 3.79534373, 3.98798262, ...
    4.19039921, 4.40308979, 4.62657583, 4.86140527];

bands_tbl = table(filter_centers', filter_sigmas', 'VariableNames', {'band_mean', 'filter_stdev'});

bands = util.table2nwb(bands_tbl, 'filter bands');

hilb_series = types.core.DecompositionSeries(...
    'data', data, ...
    'bands', bands, ...
    'metric', 'analytic amplitude', ...
    'data_unit', 'no units',...
    'source_timeseries', ECoG_soft_link);
    
ecephys_mod.nwbdatainterface.set('HilbertAA',hilb_series);
file.processing.set('ecephys', ecephys_mod);


%% write file
nwbExport(file, nwb_path)

%% test read
nwb_read = nwbRead(nwb_path);




