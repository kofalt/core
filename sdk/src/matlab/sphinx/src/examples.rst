Examples
********
This page provides some brief, minimal examples for common tasks with the SDK.

Groups
======
For managing permissions, see :ref:`data-model-permissions`.

Add Group
---------
Create a new group, with an id of ``my_group`` and a label of ``My Test Group``:

.. code-block:: matlab

	groupId = fw.addGroup('id', 'my_group', 'label', 'My Test Group');


List Groups
-----------
List all groups that I have access to:

.. code-block:: matlab

	groups = fw.groups();

	for i = 1:numel(groups) 
	  fprintf('%s: %s\n', groups{i}.id, groups{i}.label);
	end

Modify Group Tags
-----------------
Add tags named ``Control`` and ``Study`` to a group.

.. code-block:: matlab

	group = fw.get(groupId);
	group.addTag('Control');
	group.addTag('Study');

	group = group.reload();
	fprintf('%s\n', strjoin(group.tags, ', '));

List Projects in Group
----------------------
List all of the projects belonging to group.

.. code-block:: matlab

	projects = group.projects();

	for i = 1:numel(projects) 
	  fprintf('%s: %s\n', projects{i}.id, projects{i}.label);
	end

Projects
========
For managing tags, files, notes or info, see :ref:`data-model-containers`.

For managing permissions, see :ref:`data-model-permissions`.

Add Project
-----------
Create a new project that belongs to ``groupId`` with a label of ``My Test Project``.

.. code-block:: matlab

	project = group.addProject('label', 'My Test Project');

List Projects
-------------
List all of the projects that I have access to:

.. code-block:: matlab

	projects = fw.projects();

	for i = 1:numel(projects) 
	  fprintf('%s: %s\n', projects{i}.id, projects{i}.label);
	end

List Subjects in Project
------------------------
List all subjects belonging to project.

.. code-block:: matlab

	subjects = project.subjects();

	for i = 1:numel(subjects)
		fprint('%s: %s\n', subjects{i}.id, subjects{1}.label));
	end

List Sessions in Project
------------------------
List all of the sessions belonging to project.

.. code-block:: matlab

	sessions = project.sessions();

	for i = 1:numel(sessions) 
	  fprintf('%s: %s\n', sessions{i}.id, sessions{i}.label);
	end

Subjects
========
For managing tags, files, notes or info, see :ref:`data-model-containers`.

Add Subject
-----------
Create a new subject with a label of ``Subject 01``

.. code-block:: matlab

	subject = project.addSubject('label', 'Subject 01');

List Subjects
-------------
List all of the subjects that I have access to:

.. code-block:: matlab

	subjects = fw.subjects();

	for i = 1:numel(subjects)
		fprint('%s: %s\n', subjects{i}.id, subjects{1}.label));
	end	

List Sessions in Subject
------------------------
List all of the sessions belonging to subject.

.. code-block:: matlab

	sessions = subject.sessions();
	
	for i = 1:numel(sessions) 
	  fprintf('%s: %s\n', sessions{i}.id, sessions{i}.label);
	end

Modify Subject
--------------
Update the details of a subject.

.. code-block:: matlab

	subject.update( ...
		'firstname', 'John', ...
		'lastname', 'Doe', ...
		'cohort', 'Study', ...
		'type', 'human', ...
		'sex', 'male', ...
		'race', 'Unknown or Not Reported');

Sessions
========
For managing tags, files, notes or info, see :ref:`data-model-containers`.

Add Session
-----------
Create a new session with a label of ``Session 01``.

.. code-block:: matlab

	session = subject.addSession('label', 'Session 01');

List Sessions
-------------
List all of the sessions that I have access to:

.. code-block:: matlab

	sessions = fw.sessions();

	for i = 1:numel(sessions) 
	  fprintf('%s: %s\n', sessions{i}.id, sessions{i}.label);
	end

List Acquisitions in Session
----------------------------
List all of the acquisitions belonging to session.

.. code-block:: matlab

	acquisitions = session.acquisitions();

	for i = 1:numel(acquisitions) 
	  fprintf('%s: %s\n', acquisitions{i}.id, acquisitions{i}.label);
	end

Acquisitions
============
For managing tags, files, notes or info, see :ref:`data-model-containers`.

For uploading and downloading files, see :ref:`dealing-with-files`.

Add Acquisition
---------------
Create a new acquisition with a label of ``Localizer``, and upload a file.

.. code-block:: matlab

	acquisition = session.addAcquisition('label', 'Localizer');

	acquisition.uploadFile('localizer.nii.gz');

List Acquisitions
-----------------
List all of the acquisitions that I have access to:

.. code-block:: matlab

	itr = fw.acquisitions.iter();

	while itr.hasNext()
	  acquisition = itr.next();
	  fprintf('%s: %s\n', acquisition.id, acquisition.label);
	end

List Files in Acquisition
-------------------------
List all of the files on an acquisition.

.. code-block:: matlab

	for i = 1:numel(acquisition.files) 
	  fprintf('%s: %s\n', acquisition.files{i}.name);
	end


Analyses
========
NOTE: Analyses are available on Projects, Subjects, Sessions and Acquisitions.

For managing tags, files, notes or info, see :ref:`data-model-containers`.

For uploading and downloading files, see :ref:`dealing-with-files`.


Add Analysis
------------
Create a new analysis on session referencing an input file from an
acquisition, then upload a file.

.. code-block:: matlab

	file_ref = acquisition.getFile('localizer.nii.gz').ref();
	analysis = session.addAnalysis('label', 'Localizer Analysis', 'inputs', {{file_ref}});

	analysis.uploadOutput('my-analysis.csv');

List Session Analyses
---------------------
List all of the analyses belonging to session identified by ``sessionId``.

.. code-block:: matlab

	analyses = session.analyses();

	for i = 1:numel(analyses) 
	  fprintf('%s: %s\n', analyses{i}.id, analyses{i}.label);
	end

Archive Downloads
=================
Occasionally it's desirable to download all files of a given type from
one or more containers. Flywheel provides this capability in the form of
tarfile downloads. An archive can be downloaded from a single container,
or a list of containers, and can include or exclude given file types.

For example:

.. code-block:: matlab

	project = fw.lookup('flywheel/Test Project');

	% Download all NIfTI files in the project
	project.downloadTar('test-project.tar', 'includeTypes', {{'nifti'}});

	% Download all non-DICOM data from sessions created since 2018-10-31
	sessions = project.sessions.find('created>2018-10-31');
	fw.downloadTar(sessions, 'session-files.tar', 'excludeTypes', {{'dicom'}});

Jobs And Analyses
=================

Scheduling Jobs
---------------
Running a gear requires a few questions to be answered:

1. What gear to run?
++++++++++++++++++++
A gear can be located by name and (if desired) version using the resolver.
Calling ``printDetails`` will print a textual description of the gear,
including inputs and configuration values, and will help answer the remaining
questions.

For example:

.. code-block:: matlab

	% Get the latest version of the example gear
	gear = fw.lookup('gears/flywheel-example-gear');

	% Get a specific version of the example gear
	gear = fw.lookup('gears/flywheel-example-gear/0.0.4');

	% Print details about the gear
	gear.printDetails();

..

	Flywheel Example Gear

	Sample gear to demonstrate a simple use case of outputting the name of each input file.
	Name:       flywheel-example-gear
	Version:    0.0.4
	Category:   converter
	Author:     Flywheel <support@flywheel.io>
	Maintainer: Ryan Sanford <ryansanford@flywheel.io>
	URL:        https://flywheel.io/
	Source:     https://github.com/flywheel-apps/example-gear

	Inputs:
	  dicom (file, required)
	    Any dicom file.
	  file (file, required)
	    Any file.
	  text (file, required)
	    Any test file that is 10 KB in size or less.

	Configuration:
	  boolean (boolean, default: 1)
	    Any boolean.
	  integer (integer, default: 7)
	    Any integer.
	  multiple (number, default: 20)
	    Any two-digit multiple of ten.
	  number (number, default: 3.5000)
	    Any number.
	  phone (string, default: 555-5555)
	    Any local phone number, no country or area code.
	  string (string, default: Example)
	    Any string.
	  string2 (string, default: Example 2)
	    Any string from 2 to 15 characters long.

2. What type of job?
++++++++++++++++++++
There are generally two types of gears: Utility and Analysis gears.

Utility gears generally perform basic data conversion and QA tasks.
Often times they run within the context of a single container, taking
input files and generating output files and/or metadata.

Analysis gears are a bit different in that they create a new Analysis
object when they run. A destination is still specified, but rather than
outputs being attached directly to the destination container, a new
analysis is attached to that container, which contains any output files.

When executing analysis gears, an analysis label is required. The gear
``category`` (in the description above) determines whether or not a gear
is an analysis gear.

3. What are the inputs?
+++++++++++++++++++++++
Gears can specify one or more file inputs, and can designate whether those
file inputs are optional or required. It's not uncommon for the gear to also
designate an input file type.

4. Where should outputs go?
+++++++++++++++++++++++++++
In addition to the input files, a destination container for output files is required.
In the case of analysis gears, the destination will be a new analysis object
on the destination container.

5. What configuration is desired?
+++++++++++++++++++++++++++++++++
Finally, any configuration values that do not have default values, or
desirable default values should be specified at job creation time.

Utility Job Example
-------------------
The Gear object provides the ability to directly start a job:

.. code-block:: matlab

	% Get the Flywheel Example Utility gear
	gear = fw.lookup('gears/flywheel-example-gear');

	% Find the input files, acquisition will be the destination container
	acquisition = fw.lookup('flywheel/Test Project/sub-1000/session1/Scan');
	inputs = {{'dicom', acquisition.getFile('scan.dicom.zip')}, ...
		{'file', acquisition.getFile('hello-world.txt'})};

	% Override some configuration values, the rest will use defaults
	config = struct('number', 42, 'string', 'Hello World!');

	% Schedule the job, adding the "my-job" tag
	jobId = gear.run('config', config, 'inputs', inputs , 'destination', acquisition, 'tags' {{'my-job'}});


Analysis Job Example
--------------------
The main difference when running an analysis is setting a label:

.. code-block:: matlab

	% Get the afq-demo gear
	gear = fw.lookup('gears/afq-demo');

	% Find the session, which will be the destination
	session = fw.lookup('flywheel/Test Project/sub-1000/session1');

	% Determine the input files, which are on the DTI acquisition
	% Find the DTI acquisition, which contains the input files
	inputs = {{'diffusion', dti.getFile('8892_14_1_dti.nii.gz'}, ...
		{'bvec', dti.getFile('8892_14_1_dti.bvec')}, ...
		{'bval', dti.getFile('8892_14_1_dti.bval')}};

	% Set config value
	config = {{'qmr_metadata_bvalue', 2000}};

	% Schedule the job, which returns the analysis ID
	analysisId = gear.run('analysisLabel', 'My AFQ Demo', 'config', config, 'inputs', inputs, 'destination', session);


Batch Scheduling Example
------------------------
It is also possible to schedule batch jobs on a group of containers.
In this case, a job will be scheduled for each container specified that
has matching inputs. Batch scheduling happens via a proposal process.

You can also schedule batch analysis runs in this manner, by providing
an ``analysisLabel``.

For example:

.. code-block:: matlab

	% Get the dcm2niix gear
	gear = fw.lookup('gears/dcm2niix');

	% Find matching acquisitions, using regular expression match on label
	session = fw.lookup('flywheel/Test Project/sub-1000/session1');
	t1Acquisitions = session.acquisitions.find('label=~^T1');

	% Propose the batch
	proposal = gear.proposeBatch(t1Acquisitions, 'config', struct('merge2d', 'y'));

	% Run the batch job
	jobs = proposal.run();
