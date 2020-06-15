function [nwbfile, ecog_channels] = elecs2ElectrodeTable(nwbfile, elecspath)
%FILE=ELECS2ELECTRODETABLE(NWBFILE, ELECSPATH)
%   Takes a matnwb NWBFILE and the elecs .mat file path, loads in anatomical
%   and location information for each electrode, and writes this information
%   to a matnwb ElectrodeTable

elecs = load(elecspath, 'anatomy', 'elecmatrix');
location = elecs.anatomy(:,4);
x = elecs.elecmatrix(:,1);
y = elecs.elecmatrix(:,2);
z = elecs.elecmatrix(:,3);
label = elecs.anatomy(:,2);


device_labels = {};
for i = 1:length(elecs.anatomy)
    this_label = label{i};
    device_labels{i} = this_label(1:strfind(this_label, 'Electrode')-1);
end

udevice_labels = unique(device_labels, 'stable');

variables = {'id', 'x', 'y', 'z', 'imp', 'location', 'filtering', ...
    'group', 'label'};
id = 0;
for i_device = 1:length(udevice_labels)
    device_label = udevice_labels{i_device};
    if ~isempty(device_label) % take care of 'NaN' label
        
        nwbfile.general_devices.set(device_label,...
            types.core.Device());
        
        nwbfile.general_extracellular_ephys.set(device_label,...
            types.core.ElectrodeGroup( ...
            'description', 'a test ElectrodeGroup', ...
            'location', 'unknown', ...
            'device', types.untyped.SoftLink(['/general/devices/' device_label])));
        
        ov = types.untyped.ObjectView(['/general/extracellular_ephys/' device_label]);
        
        elec_nums = find(strcmp(device_labels, device_label));
        for i_elec = 1:length(elec_nums)
            elec_num = elec_nums(i_elec);
            if i_device == 1 && i_elec == 1
                tbl = table(id, x(1), y(1), z(1), NaN, location(1), {'filtering'}, ...
                    ov, label(1), 'VariableNames', variables);
            else
                tbl = [tbl; {id, x(elec_num), y(elec_num), z(elec_num), NaN,...
                    location{elec_num}, 'filtering', ov, label{elec_num}}];
            end
            id = id + 1;
        end
        
    end
end

nwbfile.general_extracellular_ephys_electrodes =  util.table2nwb(tbl, 'electrodes table');
ecog_channels = ~strcmp(device_labels,'');