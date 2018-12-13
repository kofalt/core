Data Model
**********

Hierarchy
---------
Data in a Flywheel system is organized in a tree-like hierarchy, as indicated in the following diagram.

.. image:: /../../../static/images/data-model.png

- :class:`~flywheel.model.User` - An authorized entity, usually referenced by email address.
- :class:`~flywheel.model.Group` - A grouping of users and projects.
- :class:`~flywheel.model.Project` - A project represents a grouping of subjects and sessions, e.g. within a study.
- :class:`~flywheel.model.Subject` - An individual under study.
- :class:`~flywheel.model.Session` - A grouping of acquired data, typically data acquired within a limited timeframe.
- :class:`~flywheel.model.Acquisition` - A set of one or more files, typically acquired as part of the same process, at the same time.
- :class:`~flywheel.model.AnalysisOutput` - A set of one or more derivative files from analyzing files after they have been acquired.

.. _data-model-permissions:

Permissions
-----------
Permissions in Flywheel are managed at the Group and Project level. Users that belong to a Group or a Project have a 
Role, which is one of: 

- **Admin** (``admin``) - Administrators can perform administrative-level actions such as setting permissions or creating and deleting projects.
- **Read-Write** (``rw``) - Users can read, create and delete data, but cannot assign permissions or delete entire projects.
- **Read-Only** (``ro``) - Users can only read data

By default when a new Project is created belonging to a Group, permissions will be copied from the Group to the Project, keeping
user roles intact. From that point on, permissions for that Project must be managed at that project, changes made to the Group
will not propagate to the project.

.. code-block:: matlab

	# See project permissions
	project = fw.get(projectId);
	disp(project.permissions{1});

	# Add permission to a project
	project.addPermission(flywheel.model.Permission('id', 'justinehlert@flywheel.io', 'access', 'ro'));

	# Remove permission from a project
	project.deletePermission(projectId, 'justinehlert@flywheel.io');

.. _data-model-containers:

Containers
----------
Projects, Subjects, Sessions, Acquisitions and Analyses are all different types of *Containers*. Containers in Flywheel all support 
the following features:

Tags
++++
Tags are concise labels that provide descriptive metadata that can be searched on. Available tags are managed on the Group.

.. code-block:: matlab

	# See tags on a session
	session = fw.get(sessionId);
	fprintf('%s\n', strjoin(session.tags, ', '));

	# Add a tag to a session
	session.addTag('Control');

	# Remove a tag from a session
	session.deleteTag('Analysis Required');

Notes
+++++
Notes are user-entered, human readable metadata attached to a container. They are timestamped and attributed to the user that entered them.

.. code-block:: matlab

	# See notes on a session
	session = fw.get(sessionId);
	disp(session.notes{1});

	# Add a note to a session
	session.addNote('This is a note');

	# Delete a note from a session
	session.deleteNote(session.notes{1}.id);

Info
++++

Info is free-form JSON metadata associated with a container or file.

.. code-block:: matlab

	# Print the info for an acquisition
	acquisition = fw.get(acquisitionId);
	disp(acquisition.info);

	# Replace the entire contents of acquisition info
	acquisition.replaceInfo(struct('splines', 34));

	# Add additional fields to acquisition info
	acquisition.setInfo(struct('curve', 'bezier'));

	# Delete fields from acquisition info
	acquisition.deleteInfo({{'splines'; 'bezier'}});

Files
+++++
Files are a set of file attachments associated with a container. See also :ref:`dealing-with-files`.

.. code-block:: matlab

	# List files on an acquisition
	acquisition = fw.get(acquisitionId);

	for idx = 1:numel(acquisition.files)
	  fprintf('Name: %s, type: %s\n', acquisition.files{idx}.name, acquisition.files{idx}.type);
	end

	# Upload a file to an acquisition
	acquisition.uploadFile('/path/to/file.txt');

	# Download a file to disk
	acquisition.downloadFile('file.txt', '/path/to/file.txt');

	# Files can also have metadata
	disp(acquisition.files{1}.info);

	acquisition.replaceFileInfo('file.txt', struct('wordCount', 327));

File Classification
+++++++++++++++++++
Flywheel supports an extensible, multi-dimenstional classification scheme for files. Each dimension
of classification is referred to as an aspect. The available aspects are determined by the file's
modality.

For example, the ``MR`` modality provides the ``Intent``, ``Measurement`` and ``Features`` aspects.
In addition, the ``Custom`` aspect is always available, regardless of modality.

.. code-block:: matlab

	% Display the aspects defined in the MR modality
	mr = fw.get_modality('MR');
	keys = mr.classification.keys();
	for i = 1:numel(keys)
		aspectName = keys{i};
		aspectValues = strjoin(mr.classification.(aspectName), ', ');
		fprintf('%s: %s\n', aspectName, aspectValues);
	end

	% Replace a file's modality and classification
	acquisition.replaceFileClassification('file.txt', ...
		struct('Intent', {{'Structural'}}, 'Measurement', {{'T2'}}),
		'modality', 'MR');

	% Update a file's Custom classification, without changing
	% existing values or modality
	acquisition.updateFileClassification('file.txt', ...
		struct('Custom', {{'value1', 'value2'}}));

	% Delete 'value1' from Custom classification
	acquisition.deleteFileClassification('file.txt', ...
		struct('Custom', {{'value1'}}));

Timestamps [NEW]
++++++++++++++++
Objects with timestamps and created/modified dates provide helper accessors
to get those dates in the local (system) timezone, as well as the original
timezone in the case of acquisition and session timestamps.

For example:

.. code-block:: matlab

	% Acquisition Timestamp (tz=UTC)
	disp(acquisition.timestamp);

	% Acquisition Timestamp (tz=Local Timezone)
	disp(acquisition.localTimestamp);

	% Acquisition Timestamp (tz=Original Timezone)
	disp(acquisition.originalTimestamp);

Age at Time of Session [NEW]
++++++++++++++++++++++++++++
Sessions have a field for subject age at the time of the session,
in seconds. There are also helper accessors to get age in years,
months, weeks and days.

For example:

.. code-block:: matlab

	% Subject age in seconds
	fprintf('Subject was %0.2f seconds old\n', session.age);

	% Subject age in years
	fprintf('Subject was %0.2f years old\n', session.ageYears);
