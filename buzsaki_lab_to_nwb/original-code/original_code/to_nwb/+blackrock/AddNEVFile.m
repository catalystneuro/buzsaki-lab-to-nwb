function file = AddNEVFile(file, nev, name, starting_time)

if ~exist('name','var') || isempty(name)
    name = 'spikes';
end

if ~exist('starting_time','var') || isempty(starting_time)
    starting_time = 0.0;
end

if ischar(nev)
    spikes_data = openNEV(nev);
else
    spikes_data = nev;
end
    

Spikes = spikes_data.Data.Spikes;
spike_loc = ['/acquisition/' name '/spike_times'];

[sorted_elecs, i_sort] = sort(Spikes.Electrode);
sorted_spike_times = single(Spikes.TimeStamp(i_sort))/spikes_data.MetaTags.TimeRes + starting_time;
vd = types.core.VectorData('data', sorted_spike_times);

steps = find(diff(sorted_elecs));
vd_ref = types.untyped.RegionView(spike_loc, {[1 steps(1)]});
for i = 1:length(steps)-1
    vd_ref(end+1) = types.untyped.RegionView(spike_loc, ...
        {[steps(i)+1, steps(i+1)]});
end
vd_ref(end+1) = types.untyped.RegionView(spike_loc, ...
    {[steps(i+1), length(Spikes.TimeStamp)]});

vi = types.core.VectorIndex('data', vd_ref);
ei = types.core.ElementIdentifiers('data', int64(unique(Spikes.Electrode)));
UnitTimes = types.core.UnitTimes('spike_times', vd, 'spike_times_index',...
    vi, 'unit_ids', ei);

file.acquisition.set('spikes', UnitTimes);