addpath(genpath(pwd));

generateCore('schema/core/nwb.namespace.yaml');

%% file

fpath = '/Users/bendichter/Desktop/Buzsaki/SenzaiBuzsaki2017/YutaMouse41-150903';


[fpath_base, fname, ext] = fileparts(fpath);
session_description = 'mouse in open exploration and theta maze';
identifier = fname;
session_start_time = datetime(2015, 7, 31);
institution = 'NYU';
lab = 'Buzsaki';

sessionInfo = bz_getSessionInfo(fpath, 'noPrompts', true);
samplingRate = sessionInfo.lfpSampleRate;
channel_groups = {sessionInfo.SpkGrps.Channels};



source = fname;
file = nwbfile;
file.file_create_date = {datestr(now, 'yyyy-mm-dd hh:MM:SS')};
file.identifier = {fname};
file.session_description = {fname};
file.session_start_time = {sessionInfo.Date};


%% animal position
whl_path = '/Users/bendichter/Desktop/Buzsaki/SenzaiBuzsaki2017/YutaMouse41-150903/YutaMouse41-150903.whl';
aa = dlmread(whl_path);
fs = 1250./32.;

ss = types.SpatialSeries('source',{'position sensor0'},...
    'description',{'raw sensor data from sensor 0'},...
    'data',aa(:,[1,2]),'timestamps',(1:length(aa))*fs,...
    'starting_time',0);

file.acquisition.position_sensor_0 = ss;


ss = types.SpatialSeries('source',{'position sensor1'},...
    'description',{'raw sensor data from sensor 1'},...
    'data',aa(:,[3,4]),'timestamps',(1:length(aa))*fs,...
    'starting_time',0);

file.acquisition.position_sensor_1 = ss;

%% load LFP
lfp_filepath = fullfile(fpath, [fname, '.eeg']);
lfp_file = fopen(lfp_filepath, 'r');
lfp_data = fread(lfp_file,'int16=>int16'); % takes 45 seconds 
lfp_data = reshape(lfp_data,[],sessionInfo.nChannels);

%%
lfp_data = lfp_data(1:100,:);
lfp_tt = (1:length(lfp_data)) * samplingRate;

%% construct LFP

file.general.devices = types.untyped.Group();
file.general.extracellular_ephys = types.untyped.Group();
device_links = {};
for i=1:length(channel_groups)
    device_name = ['shank', num2str(i-1)];
    dev = types.Device('source',{[fname, '.xml']});
    file.general.devices.(device_name) = dev;
    
    device_links{i} = types.untyped.Link(['/general/devices/', device_name],...
        '', dev);
    
    eg = types.ElectrodeGroup( ...
        'source', {[fname, '.xml']}, 'description', {device_name}, ...
        'location', {'unknown'}, 'device', device_links{i},...
        'channel_coordinates',{'NaN','NaN','NaN'});
    file.general.extracellular_ephys.([device_name, '_electrodes']) = eg;
    
    es = types.ElectricalSeries( ...
        'source', {'a hypothetical source'}, ...
        'data', lfp_data(:,channel_groups{i}+1), ...
        'electrode_group', types.untyped.Link(...
            ['/general/extracellular_ephys/', [device_name, '_electrodes']],...
            '', eg), ...
        'timestamps', lfp_tt');
    
    %lfp = types.LFP('source',{fname},'ElectricalSeries',es);
    file.acquisition.(['shank' num2str(i) ' lfp']) = es;
end

%% special elctrodes

special_electrode_names = {'ch_wait', 'ch_arm', 'ch_solL', 'ch_solR',...
    'ch_dig1', 'ch_dig2', 'ch_entL', 'ch_entR', 'ch_SsolL', 'ch_SsolR'};
special_electrode_numbers = [79,78,76,77,65,68,72,71,73,70];

for i=1:length(special_electrode_names)
    name = special_electrode_names{i};
    channel = special_electrode_numbers(i);
    ts = types.TimeSeries(...
        'source',{'a hypothetical source'},...
        'timestamps', lfp_tt',...
        'data',lfp_data(:,channel+1));
    
    file.acquisition.(name) = ts;

end

%% Spike times



%% Cell Types

load(fullfile(fpath_base,'DG_all_6__UnitFeatureSummary_add.mat'))
this_file = all(UnitFeatureCell.fname == fname, 2);

celltype_keys = UnitFeatureCell.fineCellType(this_file);
region_keys = UnitFeatureCell.region(this_file);
unit_id = UnitFeatureCell.unitID(this_file);


% taken from ReadMe
celltype_dict = containers.Map([0:6,8:10],...
    {'unknown',...
    'granule cells (DG) or pyramidal cells (CA3)  (need to use region info. see below.)',...
    'mossy cell',...
    'narrow waveform cell',...
    'optogenetically tagged SST cell',...
    'wide waveform cell (narrower, exclude opto tagged SST cell)',...
    'wide waveform cell (wider)',...
    'positive waveform unit (non-bursty)',...
    'positive waveform unit (bursty)',...
    'positive negative waveform unit'});

region_dict = containers.Map(3:4, {'CA3','DG'});


celltype_names = {};
for i=1:length(celltype_keys)
    if celltype_keys(i) == 1
        if region_keys(i) == 3
            celltype_names{i} = 'pyramidal cell';
        elseif region_keys(i) == 4
            celltype_names{i} = 'granule cell';
        end
    else
        celltype_names{i} = celltype_dict(celltype_keys(i));
    end
end

[u_cats, ~, indices] = unique(celltype_names);

%%

nwbExport(file, '/Users/bendichter/Desktop/mattest.nwb');





