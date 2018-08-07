% Generate a random group name
symbols = 'abcdefghijklmnopqrstuvwxyz';
nums = randi(numel(symbols),[1 16]);
testString = symbols(nums);

% Initialize API Client
apiKey = getenv('SdkTestKey');
fw = flywheel.Flywheel(apiKey);

groupId = [];
projectId = [];

try
    %% Create group, project, sessions
    disp('Creating test data')
    
    groupId = fw.addGroup(struct('id',testString));
    projectId = fw.addProject(struct('group', groupId,...
        'label', 'Data View Test'));
    
    subject1 = struct('code', '1001', 'sex', 'male', 'age', 35 * 31557600);
    subject2 = struct('code', '1002', 'sex', 'female', 'age', 37 * 31557600);
    
    session1Id = fw.addSession(struct('project', projectId, 'subject', ...
        subject1, 'label', '01'));
    acquisition1Id = fw.addAcquisition(struct('session', session1Id, ...
        'label', 'Mean Diffusivity'));
    fw.uploadFileToAcquisition(acquisition1Id, 'data/mean-diff1.csv');
    
    session2Id = fw.addSession(struct('project', projectId, 'subject', ...
        subject2, 'label', '01'));
    acquisition2Id = fw.addAcquisition(struct('session', session2Id, ...
        'label', 'Mean Diffusivity'));
    fw.uploadFileToAcquisition(acquisition2Id, 'data/mean-diff2.csv');
    
    %% Create and execute view for subject data
    disp('Verifying subject data')
    
    view = fw.View('columns', { {'subject'}, {'subject.age_years'} });
    result = fw.readViewStruct(view, projectId);
    
    assert(numel(result) == 2)
    
    assert(strcmp(result(1).subject_label, '1001'))
    assert(strcmp(result(1).subject_sex, 'male'))
    assert(result(1).subject_age_years == 35.0);

    assert(strcmp(result(2).subject_label, '1002'))
    assert(strcmp(result(2).subject_sex, 'female'))
    assert(result(2).subject_age_years == 37.0);
    
    %% Create and execute view for file names
    disp('Verifying file names')
    
    view = fw.View('columns', {{ 'acquisition.file' }});
    result = fw.readViewStruct(view, projectId);
    
    assert(numel(result) == 2)
    
    assert(strcmp(result(1).subject_label, '1001'))
    assert(strcmp(result(1).session_label, '01'))
    assert(strcmp(result(1).acquisition_label, 'Mean Diffusivity'))
    assert(strcmp(result(1).acquisition_file_name, 'mean-diff1.csv'))

    assert(strcmp(result(2).subject_label, '1002'))
    assert(strcmp(result(2).session_label, '01'))
    assert(strcmp(result(2).acquisition_label, 'Mean Diffusivity'))
    assert(strcmp(result(2).acquisition_file_name, 'mean-diff2.csv'))
    
    %% Create and execute view for file data, retyping columns
    disp('Verifying file data')
    builder = flywheel.ViewBuilder('container', 'acquisition',...
        'filename', 'mean-diff?.csv');
    builder.fileColumn('Left_Corticospinal', 'LC', 'type', 'float');
    builder.fileColumn('Right_Corticospinal', 'RC', 'type', 'float');
    view = builder.build();
    
    result = fw.readViewStruct(view, projectId);
    
    assert(numel(result) == 200)
    
    % Spot check fields
    assert(strcmp(result(1).subject_label, '1001'))
    assert(strcmp(result(101).subject_label, '1002'))
    
    % Check sums of rows
    sumLC = sum([result.LC]);
    sumRC = sum([result.RC]);
    assert(abs(156.7389 - sumLC) < 0.001)
    assert(abs(153.1726 - sumRC) < 0.001)
    
    disp('All tests passed!')
catch ME
    disp(getReport(ME));
end

%% cleanup
if ~isempty(projectId)
    fw.deleteProject(projectId);
end

if ~isempty(groupId)
    fw.deleteGroup(groupId);
end
