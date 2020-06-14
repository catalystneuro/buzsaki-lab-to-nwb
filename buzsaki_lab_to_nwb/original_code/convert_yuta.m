
addpath(genpath(pwd)); % Cody: when run from the YutaMouse41-150903
addpath(genpath('D:/GitHub/matnwb'))
addpath(genpath('D:/GitHub/buzcode')) % Cody: needed for current session read method

%generateCore()
%generateCore('schema/core/nwb.namespace.yaml');


%% file

%fpath = '/Users/bendichter/Desktop/Buzsaki/SenzaiBuzsaki2017/YutaMouse41-150903';
fpath = 'D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903';

[fpath_base, fname, ext] = fileparts(fpath);
session_description = 'mouse in open exploration and theta maze';
identifier = fname;
session_start_time = datetime(2015, 7, 31); % (Y,M,D)
institution = 'NYU';
lab = 'Buzsaki';

%sessionInfo = bz_getSessionInfo(fpath, 'noPrompts', true); % Cody: outdated version of retrieving session info
sessionInfo = LoadParameters('YutaMouse41-150903.xml'); % Cody: this is new version
samplingRate = sessionInfo.lfpSampleRate; % units? assume kHz
channel_groups = {sessionInfo.SpkGrps.Channels};


% Cody: This is the original code
%
%source = fname;
%file = nwbfile;
%file.file_create_date = {datestr(now, 'yyyy-mm-dd hh:MM:SS')};
%file.identifier = {fname};
%file.session_description = {fname};
%file.session_start_time = {sessionInfo.Date};

% Cody: This is the new code
nwb = NwbFile( ...
    'session_description', 'mouse in open exploration and theta maze', ...
    'file_create_date', datestr(now, 'yyyy-mm-dd hh:MM:SS'), ...
    'identifier', fname, ...
    'session_start_time', session_start_time, ...
    'general_experimenter', 'Yuta Senzai', ...
    'general_session_id', sessionInfo.session.name((strfind(sessionInfo.session.name,'-')+1):end), ...
    'general_institution', 'NYU');


%%
nwb.general_subject = types.core.Subject( ...
    'subject_id', '41', ...
    'description', 'Yuta mouse 41', ...
    'genotype', '', ... % unknown
    'sex', 'U', ...
    'species', 'Mus musculus');


%% animal position
%whl_path = '/Users/bendichter/Desktop/Buzsaki/SenzaiBuzsaki2017/YutaMouse41-150903/YutaMouse41-150903.whl';
whl_path = 'D:\BuzsakiData\SenzaiY\YutaMouse41\YutaMouse41-150903\YutaMouse41-150903.whl';
aa = dlmread(whl_path);
fs = samplingRate / 32; % ? Cody: what is this for and what are the units?
% Cody: figured out first part, 1250 is the lfp sample rate from session info

nTimeStamps = length(aa);
TimeStamps = (1:nTimeStamps)*fs;

% Cody: this is the original code
% ss = types.SpatialSeries('source',{'position sensor0'},...
%     'description',{'raw sensor data from sensor 0'},...
%     'data',aa(:,1:2),'timestamps',TimeStamps,...
%     'starting_time',0);
% 
% file.acquisition.position_sensor_0 = ss;
% 
% 
% ss = types.SpatialSeries('source',{'position sensor1'},...
%     'description',{'raw sensor data from sensor 1'},...
%     'data',aa(:,3:4),'timestamps',TimeStamps,...
%     'starting_time',0);
% 
% file.acquisition.position_sensor_1 = ss;

% Cody: This is the new code
spatial_series_0 = types.core.SpatialSeries( ...
    'data', aa(:,1:2), ...
    'reference_frame', 'unknown', ...
    'description', 'raw sensor data from sensor 0', ...
    'timestamps', TimeStamps);

spatial_series_1 = types.core.SpatialSeries( ...
    'data', aa(:,3:4), ...
    'reference_frame', 'unknown', ...
    'description', 'raw sensor data from sensor 1', ...
    'timestamps', TimeStamps);

Position_0 = types.core.Position('SpatialSeries', spatial_series_0);
Position_1 = types.core.Position('SpatialSeries', spatial_series_1);

behavior_mod_0 = types.core.ProcessingModule( ...
    'description',  'contains behavioral data');
behavior_mod_1 = types.core.ProcessingModule( ...
    'description',  'contains behavioral data');

behavior_mod_0.nwbdatainterface.set(...
    'Position', Position_0);
behavior_mod_1.nwbdatainterface.set(...
    'Position', Position_1);

nwb.processing.set('behavior', behavior_mod_0);
nwb.processing.set('behavior', behavior_mod_1);

clear nTimeStamps TimeStamps


%% load LFP
lfp_filepath = fullfile(fpath, [fname, '.eeg']);
lfp_file = fopen(lfp_filepath, 'r');
fprintf('\nBeginning data load...')
tic
lfp_data = fread(lfp_file,'int16=>int16'); % takes ~45 seconds
fprintf('Finished! Data took %0.2f minutes to load.\n\n',toc/60) % Cody: also about 8 GB; just about capping local RAM
lfp_data = reshape(lfp_data,[],sessionInfo.nChannels); % Cody: assume stacking method words


%%
truncateTime = 1e2; % arbitrary?
lfp_data = lfp_data(1:truncateTime,:); % Cody: truncating? certainly eases the memory
lfp_tt = (1:truncateTime) * samplingRate;


%% construct LFP, Cody: old version
% file.general.devices = types.untyped.Group();
% file.general.extracellular_ephys = types.untyped.Group();
% device_links = {};
% for i=1:length(channel_groups)
%     device_name = ['shank', num2str(i-1)];
%     dev = types.Device('source',{[fname, '.xml']});
%     file.general.devices.(device_name) = dev;
%     
%     device_links{i} = types.untyped.Link(['/general/devices/', device_name],...
%         '', dev);
%     
%     eg = types.ElectrodeGroup( ...
%         'source', {[fname, '.xml']}, 'description', {device_name}, ...
%         'location', {'unknown'}, 'device', device_links{i},...
%         'channel_coordinates',{'NaN','NaN','NaN'});
%     file.general.extracellular_ephys.([device_name, '_electrodes']) = eg;
%     
%     es = types.ElectricalSeries( ...
%         'source', {'a hypothetical source'}, ...
%         'data', lfp_data(:,channel_groups{i}+1), ...
%         'electrode_group', types.untyped.Link(...
%             ['/general/extracellular_ephys/', [device_name, '_electrodes']],...
%             '', eg), ...
%         'timestamps', lfp_tt');
%     
%     %lfp = types.LFP('source',{fname},'ElectricalSeries',es);
%     file.acquisition.(['shank' num2str(i) ' lfp']) = es;
% end


%% Cody: new version
nshanks = length(channel_groups);
variables = {'x', 'y', 'z', 'impudence', 'location', 'filtering', 'group', 'label'};
tbl = cell2table(cell(0, length(variables)), 'VariableNames', variables);

% Cody: can't find device information
device = types.core.Device(...
    'description', '', ...
    'manufacturer', '');
device_name = 'unknown';
nwb.general_devices.set(device_name, device);
device_link = types.untyped.SoftLink(['/general/devices/' device_name]);
% ------------------

for ishank = 1:nshanks
    group_name = ['shank' num2str(ishank)];
    nwb.general_extracellular_ephys.set(group_name, ...
        types.core.ElectrodeGroup( ...
            'description', ['electrode group for shank' num2str(ishank)], ...
   	        'location', 'unknown', ... % is 'unknown' correct standard for this? documentation doesn't indicate in either MatNWB or NWB itself
   	        'device', device_link));
    group_object_view = types.untyped.ObjectView( ...
       	['/general/extracellular_ephys/' group_name]);

    for ielec = 1:numel(channel_groups{ishank})
        tbl = [tbl; {NaN, NaN, NaN, NaN, 'unknown', 'unknown', ...
            group_object_view, [group_name 'elec' num2str(ielec)]}];
    end
end

electrode_table = util.table2nwb(tbl, 'all electrodes');
nwb.general_extracellular_ephys_electrodes = electrode_table;


%%
electrodes_object_view = types.untyped.ObjectView( ...
    '/general/extracellular_ephys/electrodes');

electrode_table_region = types.hdmf_common.DynamicTableRegion( ...
    'table', electrodes_object_view, ...
    'description', 'all electrodes', ...
    'data', [0 height(tbl)-1]');

ecephys_module = types.core.ProcessingModule(...
    'description', 'extracellular electrophysiology');

for ishank = 1:nshanks
    electrical_series = types.core.ElectricalSeries( ...
        'timestamps', lfp_tt', ...
        'data', lfp_data(:,channel_groups{ishank}+1), ...
        'electrodes', electrode_table_region, ... % Cody: should this subset the table?
        'data_unit', 'V'); % Cody: assuming 'V' is correct

    % Cody: including the lfp conversion and integration into the nwb
    % inside this loop, on a per shank basism siliar to done previously.
    % Is this correct?
    nwb.acquisition.set(['multielectrode_recording_shank_' num2str(ishank)], electrical_series);
    
    ecephys_module.nwbdatainterface.set('LFP', types.core.LFP( ...
        'ElectricalSeries', electrical_series));
    nwb.processing.set('ecephys', ecephys_module);
end


%% special elctrodes
% Cody: unsure how to deal with this yet
%
% special_electrode_names = {'ch_wait', 'ch_arm', 'ch_solL', 'ch_solR',...
%     'ch_dig1', 'ch_dig2', 'ch_entL', 'ch_entR', 'ch_SsolL', 'ch_SsolR'};
% special_electrode_numbers = [79,78,76,77,65,68,72,71,73,70];
% 
% for i=1:length(special_electrode_names)
%     name = special_electrode_names{i};
%     channel = special_electrode_numbers(i);
%     ts = types.TimeSeries(...
%         'source',{'a hypothetical source'},...
%         'timestamps', lfp_tt',...
%         'data',lfp_data(:,channel+1));
%     
%     file.acquisition.(name) = ts;
% 
% end


%% Spike times
%Cody: ...empty?


%% Cell Types
%
% Cody: these aren't added to the nwb in any way...
% 
% load(fullfile(fpath_base,'DG_all_6__UnitFeatureSummary_add.mat'))
% this_file = all(UnitFeatureCell.fname == fname, 2);
% 
% celltype_keys = UnitFeatureCell.fineCellType(this_file);
% region_keys = UnitFeatureCell.region(this_file);
% unit_id = UnitFeatureCell.unitID(this_file);
% 
% 
% % taken from ReadMe
% celltype_dict = containers.Map([0:6,8:10],...
%     {'unknown',...
%     'granule cells (DG) or pyramidal cells (CA3)  (need to use region info. see below.)',...
%     'mossy cell',...
%     'narrow waveform cell',...
%     'optogenetically tagged SST cell',...
%     'wide waveform cell (narrower, exclude opto tagged SST cell)',...
%     'wide waveform cell (wider)',...
%     'positive waveform unit (non-bursty)',...
%     'positive waveform unit (bursty)',...
%     'positive negative waveform unit'});
% 
% region_dict = containers.Map(3:4, {'CA3','DG'});
% 
% 
% celltype_names = {};
% for i=1:length(celltype_keys)
%     if celltype_keys(i) == 1
%         if region_keys(i) == 3
%             celltype_names{i} = 'pyramidal cell';
%         elseif region_keys(i) == 4
%             celltype_names{i} = 'granule cell';
%         end
%     else
%         celltype_names{i} = celltype_dict(celltype_keys(i));
%     end
% end
% 
% [u_cats, ~, indices] = unique(celltype_names);


%%
% Cody: original
%nwbExport(file, '/Users/bendichter/Desktop/mattest.nwb');

% Cody: new
nwbExport(nwb, [sessionInfo.session.name '.nwb'])


