function output = pull_varargin(varargin, prefix)
%PULL_VARARGIN takes name-value pairs from VARARGIN where the labels match the given prefix

output = {};

labels = varargin(1:2:end);
for i = 1:length(labels)
    label = labels{i};
    if startsWith(label, prefix)
        output{end+1} = label(length(prefix) + 2:end);
        output(end+1) = varargin(2*i);
    end
end

end