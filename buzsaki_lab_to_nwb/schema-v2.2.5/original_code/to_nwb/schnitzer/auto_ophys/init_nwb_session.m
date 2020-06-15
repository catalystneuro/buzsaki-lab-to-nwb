function nwb = init_nwb_session(varargin)

p = inputParser;
p.KeepUnmatched = true;
p.PartialMatching = false;
p.StructExpand = false;
addParameter(p, 'subject_description', 'no description');
parse(p, varargin{:});


subject_description = p.Results.subject_description;


file_varargin = pull_varargin(varargin, 'file');
nwb = nwbfile(file_varargin{:});

subject_varargin = pull_varargin(varargin, 'subject');
nwb.general_subject = types.core.Subject( ...
    'description', subject_description, ...
    subject_varargin{:});
