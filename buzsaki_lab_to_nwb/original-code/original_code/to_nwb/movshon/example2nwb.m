

addpath(genpath('~/dev/NPMK'));
%%
basepath = '/Users/bendichter/Desktop/Movshon/data/Data_BlackRock_MWorks_forBenDichter';
fname = 'HT_V4_Textures2_200stimoff_180716_001';
fname2 = 'HT_V4IT_Textures2_200stimoff_180716_001';
ns_path = fullfile(basepath, [fname '.ns6']);
nwb_path = fullfile(basepath, [fname '.nwb']);
nev_path = fullfile(basepath, [fname '.nev']);
mwk_path = fullfile(basepath, [fname2 '.mwk']);
mworks_converted_path = fullfile(basepath, [fname2 '.mwk'],...
    [fname2 '_mworks_all_output.mat']);

%%
NS = openNSx(ns_path);
%%
NEV = openNEV(nev_path);
%%
times = align_nev_to_mwk(mwk_path, NEV);
NEV_starting_time = times.NEV_time_us(1) / 1000000;

in_seconds = [0,0,0,3600*24,3600,60,1,1/1000];
NS_delay = dot(in_seconds,NS.MetaTags.DateTimeRaw - NEV.MetaTags.DateTimeRaw);
NS_starting_time = NEV_starting_time + NS_delay;
%%
date = NEV.MetaTags.DateTimeRaw([1:2,4:7]); % ignore milliseconds, and 3rd element?

file = nwbfile( ...
    'source', fname, ...
    'session_description', 'a test NWB File', ...
    'identifier', fname, ...
    'session_start_time', datestr(date, 'yyyy-mm-dd HH:MM:SS'), ...
    'file_create_date', datestr(now, 'yyyy-mm-dd HH:MM:SS'));

%%
file = blackrock.AddNSFile(file, NS, NS_starting_time);
%%
file = blackrock.AddNEVFile(file, NEV, NEV_starting_time);
%%
file = mworks.AddEyePos(file, mwk_path, {'eye_h', 'eye_v'});
%% write file
nwbExport(file, nwb_path)

%% test read
nwb_read = nwbRead(nwb_path);