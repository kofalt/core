% Query parameters
projectQuery = 'Test';
fileQuery = 'alice.txt';

apiKey = getenv('SdkTestKey');
fw = flywheel.Flywheel(apiKey);

results = fw.search(struct('returnType', 'project', 'searchString', projectQuery));
if isempty(results)
    fprintf('ERROR: No results returned!\n');
end

for i = 1:numel(results)
    result = results{i};
    fprintf('Project: %s\n', result.project.label);
    
    for j = 1:numel(result.project.files)
        file = result.project.files{j};
        fprintf('  file: %s\n', file.name);
    end
    
    for j = 1:numel(result.project.sessions)
        session = result.project.sessions{j};
        fprintf('  session: %s\n', session.label);
    end
end

results = fw.search(struct('returnType', 'file', 'searchString', fileQuery));
for i = 1:numel(results)
    result = results{i};
    fprintf('File: %s\n', result.file.name);
    fprintf('  url: %s\n', result.file.url);
end
