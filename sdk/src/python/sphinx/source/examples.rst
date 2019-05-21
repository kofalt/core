Examples
********
This page provides some brief, minimal examples for common tasks with the SDK.

Groups
======
For managing permissions, see :ref:`data-model-permissions`.

Add Group
---------
Create a new group, with an id of ``my_group`` and a label of ``My Test Group``:

.. code-block:: python

	group_id = fw.add_group(flywheel.Group('my_group', 'My Test Group'))


List Groups
-----------
List all groups that I have access to:

.. code-block:: python

	for group in fw.groups():
	  print('%s: %s' % (group.id, group.label))

Modify Group Tags
-----------------
Add tags named ``Control`` and ``Study`` to a group.

.. code-block:: python

	group = fw.get(group_id)
	group.add_tag('Control')
	group.add_tag('Study')

	group = group.reload()
	print(', '.join(group.tags))

List Projects in Group
----------------------
List all of the projects belonging to group.

.. code-block:: python

	for project in group.projects():
	  print('%s: %s' % (project.id, project.label))

Projects
========
For managing tags, files, notes or info, see :ref:`data-model-containers`.

For managing permissions, see :ref:`data-model-permissions`.

Add Project
-----------
Create a new project that belongs to ``group_id`` with a label of ``My Test Project``.

.. code-block:: python

	project = group.add_project(label='My Test Project')

List Projects
-------------
List all of the projects that I have access to:

.. code-block:: python

	for project in fw.projects():
	  print('%s: %s' % (project.id, project.label))

List Subjects in Project
------------------------
List all subjects belonging to project.

.. code-block:: python

	for subject in project.subjects():
		print('%s: %s' % (subject.id, subject.label))


List Sessions in Project
------------------------
List all of the sessions belonging to project.

.. code-block:: python

	for session in project.sessions():
		print('%s: %s' % (session.id, session.label))

Subjects
========
For managing tags, files, notes or info, see :ref:`data-model-containers`.

Add Subject
-----------
Create a new subject with a label of ``Subject 01``

.. code-block:: python

	subject = project.add_subject(label='Subject 01')

List Subjects
-------------
List all of the subjects that I have access to:

.. code-block:: python

	for subject in fw.subjects():
		print('%s: %s' % (subject.id, subject.label))

List Sessions in Subject
------------------------
List all of the sessions belonging to subject.

.. code-block:: python

	for session in subject.sessions():
		print('%s: %s' % (session.id, session.label))

Modify Subject
--------------
Update the details of a subject

.. code-block:: python

	subject.update(
		firstname='John',
		lastname='Doe',
		cohort='Study',
		type='human',
		sex='male',
		race='Unknown or Not Reported'
	)

Sessions
========
For managing tags, files, notes or info, see :ref:`data-model-containers`.

Add Session
-----------
Create a new session with a label of ``Session 01``.

.. code-block:: python

	session = subject.add_session(label='Session 01')

List Sessions
-------------
List all of the sessions that I have access to:

.. code-block:: python

	for session in fw.sessions():
		print('%s: %s' % (session.id, session.label))

List Acquisitions in Session
----------------------------
List all of the acquisitions belonging to session.

.. code-block:: python

	for acquisition in session.acquisitions():
	  print('%s: %s' % (acquisition.id, acquisition.label))

Acquisitions
============
For managing tags, files, notes or info, see :ref:`data-model-containers`.

For uploading and downloading files, see :ref:`dealing-with-files`.

Add Acquisition
---------------
Create a new acquisition with a label of ``Localizer``, and upload a file.

.. code-block:: python

	acquisition = session.add_acquisition(label='Localizer')

	acquisition.upload_file('localizer.nii.gz')

List Acquisitions
-----------------
List all of the acquisitions that I have access to:

.. code-block:: python

	for acquisition in fw.acquisitions.iter():
	  print('%s: %s' % (acquisition.id, acquisition.label))

List Files in Acquisition
-------------------------
List all of the files on an acquisition.

.. code-block:: python

	for file in acquisition.files:
	  print(file.name)

Analyses
========
NOTE: Analyses are available on Projects, Subjects, Sessions and Acquisitions.

For managing tags, files, notes or info, see :ref:`data-model-containers`.

For uploading and downloading files, see :ref:`dealing-with-files`.


Add Analysis
------------
Create a new analysis on session referencing an input file from an
acquisition, then upload a file.

.. code-block:: python

	file_ref = acquisition.get_file('localizer.nii.gz').ref()
	analysis = session.add_analysis(label='Localizer Analysis', inputs=[file_ref])

	analysis.upload_output('my-analysis.csv')

List Session Analyses
---------------------
List all of the analyses belonging to session.

.. code-block:: python

	for analysis in session.analyses():
		print('%s: %s' % (analysis.id, analysis.label))

Archive Downloads
=================
Occasionally it's desirable to download all files of a given type from
one or more containers. Flywheel provides this capability in the form of
tarfile downloads. An archive can be downloaded from a single container,
or a list of containers, and can include or exclude given file types.

For example:

.. code-block:: python

	project = fw.lookup('flywheel/Test Project')

	# Download all NIfTI files in the project
	project.download_tar('test-project.tar', include_types=['nifti'])

	# Download all non-DICOM data from sessions created since 2018-10-31
	sessions = project.sessions.find('created>2018-10-31')
	fw.download_tar(sessions, 'session-files.tar', exclude_types=['dicom'])

Jobs And Analyses
=================

Scheduling Jobs
---------------
Running a gear requires a few questions to be answered:

1. What gear to run?
++++++++++++++++++++
A gear can be located by name and (if desired) version using the resolver.
Calling ``print_details`` will print a textual description of the gear,
including inputs and configuration values, and will help answer the remaining
questions.

For example:

.. code-block:: python

	# Get the latest version of the example gear
	gear = fw.lookup('gears/flywheel-example-gear')

	# Get a specific version of the example gear
	gear = fw.lookup('gears/flywheel-example-gear/0.0.4')

	# Print details about the gear
	gear.print_details()

..

	Flywheel Example Gear

	Sample gear to demonstrate a simple use case of outputting the name of each input file.

	Name:           flywheel-example-gear
	Version:        0.0.4
	Category:       converter
	Author:         Flywheel <support@flywheel.io>
	Maintainer:     Ryan Sanford <ryansanford@flywheel.io>
	URL:            https://flywheel.io/
	Source:         https://github.com/flywheel-apps/example-gear

	Inputs:
	  dicom (file, required)
	    Type: dicom
	    Any dicom file.
	  file (file, required)
	    Any file.
	  text (file, optional)
	    Any test file that is 10 KB in size or less.

	Configuration:
	  multiple (number, default: 20)
	    Any two-digit multiple of ten.
	  string (string, default: Example)
	    Any string.
	  number (number, default: 3.5)
	    Any number.
	  phone (string, default: 555-5555)
	    Any local phone number, no country or area code.
	  boolean (boolean, default: True)
	    Any boolean.
	  integer (integer, default: 7)
	    Any integer.
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

.. code-block:: python

	# Get the Flywheel Example Utility gear
	gear = fw.lookup('gears/flywheel-example-gear')

	# Find the input files, acquisition will be the destination container
	acquisition = fw.lookup('flywheel/Test Project/sub-1000/session1/Scan')
	inputs = {
		'dicom': acquisition.get_file('scan.dicom.zip'),
		'file': acquisition.get_file('hello-world.txt')
	}

	# Override some configuration values, the rest will use defaults
	config = {
		'number': 42,
		'string': 'Hello World!'
	}

	# Schedule the job, adding the "my-job" tag
	job_id = gear.run(config=config, inputs=inputs, destination=acquisition, tags=['my-job'])


Analysis Job Example
--------------------
The main difference when running an analysis is setting a label:

.. code-block:: python

	# Get the afq-demo gear
	gear = fw.lookup('gears/afq-demo')

	# Find the session, which will be the destination
	session = fw.lookup('flywheel/Test Project/sub-1000/session1')

	# Determine the input files, which are on the DTI acquisition
	# Find the DTI acquisition, which contains the input files
	inputs = {
		'diffusion': dti.get_file('8892_14_1_dti.nii.gz'),
		'bvec': dti.get_file('8892_14_1_dti.bvec'),
		'bval': dti.get_file('8892_14_1_dti.bval')
	}

	# Set config value
	config = {
		'qmr_metadata_bvalue': 2000
	}

	# Schedule the job, which returns the analysis ID
	analysis_id = gear.run(analysis_label='My AFQ Demo', config=config, inputs=inputs, destination=session)


Batch Scheduling Example
------------------------
It is also possible to schedule batch jobs on a group of containers.
In this case, a job will be scheduled for each container specified that
has matching inputs. Batch scheduling happens via a proposal process.

You can also schedule batch analysis runs in this manner, by providing
an ``analysis_label``.

For example:

.. code-block:: python

	# Get the dcm2niix gear
	gear = fw.lookup('gears/dcm2niix')

	# Find matching acquisitions, using regular expression match on label
	session = fw.lookup('flywheel/Test Project/sub-1000/session1')
	t1_acquisitions = session.acquisitions.find('label=~^T1')

	# Propose the batch
	proposal = gear.propose_batch(t1_acquisitions, config={'merge2d': 'y'})

	# Run the batch job
	jobs = proposal.run()
