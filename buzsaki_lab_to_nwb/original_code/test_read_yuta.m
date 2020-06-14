
addpath(genpath(pwd)); % Cody: when run from the YutaMouse41-150903
addpath(genpath('D:/GitHub/matnwb'))
addpath(genpath('D:/GitHub/buzcode')) % Cody: needed for current session read method

% Cody: expects to be in the data file
nwb = nwbRead('YutaMouse41-150903.nwb');


%% Reading data
disp(nwb.acquisition.get('multielectrode_recording_shank_1').data)

data = nwb.acquisition.get('multielectrode_recording_shank_1').data.load;
disp(data(1:5, 1:3));

nwb.acquisition.get('multielectrode_recording_shank_1').data.load([1,1], [5,3])

