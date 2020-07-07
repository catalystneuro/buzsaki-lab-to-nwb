
addpath(genpath(pwd)); % Cody: when run from the YutaMouse41-150903
addpath(genpath('D:/GitHub/matnwb'))
addpath(genpath('D:/GitHub/buzcode')) % Cody: needed for current session read method

% Cody: expects to be in the data file
nwbTest = nwbRead('YutaMouse41-150903.nwb');


%% Reading data
disp(nwbTest.acquisition.get('multielectrode_recording_shank_1').data)

data = nwbTest.acquisition.get('multielectrode_recording_shank_1').data.load;
disp(data(1:5, 1:3));

nwbTest.acquisition.get('multielectrode_recording_shank_1').data.load([1,1], [5,3])


%%
nwbActual = nwbRead('sub-YutaMouse41_ses-YutaMouse41-150903_behavior+ecephys.nwb');

% Cody: getting a schema issue b/c this is in v2.0b format whereas nwb
% scheme for matnwb as of 6/14/2020 is v2.2.5


%% Reading data
disp(nwbActual.acquisition.get('multielectrode_recording_shank_1').data)

data = nwbActual.acquisition.get('multielectrode_recording_shank_1').data.load;
disp(data(1:5, 1:3));

nwbActual.acquisition.get('multielectrode_recording_shank_1').data.load([1,1], [5,3])

