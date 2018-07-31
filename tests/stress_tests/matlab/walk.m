% Usage: matlab -r walk('api-key', 1)
function walk(apiKey, root)
    fw = flywheel.Flywheel(apiKey, root);
    
    % Walk projects
    projects = fw.getAllProjects();
    for i = 1:numel(projects)
        walkProject(fw, projects{i});
    end
    
    % Walk collections
    collections = fw.getAllCollections();
    for i = 1:numel(collections)
        walkCollection(fw, collections{i});
    end    
end

function walkCollection(fw, collection)
    fprintf('Collection: %s\n', collection.label);
    try
        % Re-retrieve
        collection = fw.getCollection(collection.id);
        
        % Get sessions
        sessions = fw.getCollectionSessions(collection.id);
        for i = 1:numel(sessions)
            walkSession(fw, sessions{i});
        end
        
        % Get acquisitions
        acquisitions = fw.getCollectionAcquisitions(collection.id);
        for i = 1:numel(acquisitions)
            walkAcquisition(fw, acquisitions{i});
        end
    catch ME
        reportError('collection', collection, ME);
    end
end

function walkProject(fw, project)
    fprintf('Project: %s\n', project.label);
    try
        % Re-retrieve
        project = fw.getProject(project.id);
        
        % Get sessions
        sessions = fw.getProjectSessions(project.id);
        for i = 1:numel(sessions)
            walkSession(fw, sessions{i});
        end
        
        fw.getProjectAnalyses(project.id);
    catch ME
        reportError('project', project, ME);
    end
end

function walkSession(fw, session)
    fprintf('  Session: %s\n', session.label);
    try
        % Re-retrieve
        session = fw.getSession(session.id);
        
        % Get acquisitions
        acquisitions = fw.getSessionAcquisitions(session.id);
        for i = 1:numel(acquisitions)
            walkAcquisition(fw, acquisitions{i});
        end
        
        fw.getSessionAnalyses(session.id);
    catch ME
        reportError('session', session, ME);
    end
end

function walkAcquisition(fw, acquisition)
    fprintf('    Acquisition: %s\n', acquisition.label);
    try
        % Re-retrieve
        acquisition = fw.getAcquisition(acquisition.id);
        fw.getAcquisitionAnalyses(acquisition.id);
    catch ME
        reportError('acquisition', acquisition, ME);
    end
end

function reportError(contType, cont, ME)
    fprintf('ERROR: %s %s - %s\n', contType, cont.id, getReport(ME, 'basic'));
end
