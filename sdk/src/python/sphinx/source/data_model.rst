Data Model
**********

Hierarchy
---------
Data in a Flywheel system is organized in a tree-like hierarchy, as indicated in the following diagram.

.. image:: /../../../static/images/data-model.png

- :class:`flywheel.models.user.User` - An authorized entity, usually referenced by email address.
- :class:`flywheel.models.group.Group` - A grouping of users and projects.
- :class:`flywheel.models.project.Project` - A project represents a grouping of subjects and sessions, e.g. within a study.
- :class:`flywheel.models.subject.Subject` - An individual under study.
- :class:`flywheel.models.session.Session` - A grouping of acquired data, typically data acquired within a limited timeframe.
- :class:`flywheel.models.acquisition.Acquisition` - A set of one or more files, typically acquired as part of the same process, at the same time.
- :class:`flywheel.models.analysis_output.AnalysisOutput` - A set of one or more derivative files from analyzing files after they have been acquired.

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

.. code-block:: python

	from pprint import pprint

	# See project permissions
	project = fw.get(project_id)
	pprint(project.permissions)

	# Add permission to a project
	project.add_permission(flywheel.Permission('justinehlert@flywheel.io', 'ro'))

	# Remove permission from a project
	project.delete_permission('justinehlert@flywheel.io')

.. _data-model-containers:

Containers
----------
Projects, Subjects, Sessions, Acquisitions and Analyses are all different types of *Containers*. Containers in Flywheel all support 
the following features:

Tags
++++
Tags are concise labels that provide descriptive metadata that can be searched on. Available tags are managed on the Group.

.. code-block:: python

	# See tags on a session
	session = fw.get(session_id)
	print(', '.join(session.tags))

	# Add a tag to a session
	session.add_tag('Control')

	# Remove a tag from a session
	session.delete_tag('Analysis Required')

Notes
+++++
Notes are user-entered, human readable metadata attached to a container. They are timestamped and attributed to the user that entered them.

.. code-block:: python

	from pprint import pprint

	# See notes on a session
	session = fw.get(session_id)
	pprint(session.notes)

	# Add a note to a session
	session.add_note('This is a note')

	# Delete a note from a session
	session.delete_note(session.notes[0].id)

Info
++++

Info is free-form JSON metadata associated with a container or file.

.. code-block:: python

	from pprint import pprint

	# Print the info for an acquisition
	acquisition = fw.get(acquisition_id)
	pprint(acquisition.info)

	# Replace the entire contents of acquisition info
	acquisition.replace_info({ 'splines': 34 })

	# Add additional fields to acquisition info
	acquisition.update_info({ 'curve': 'bezier' })

	# Delete fields from acquisition info
	acquisition.delete_info('splines')

Files
+++++
Files are a set of file attachments associated with a container. See also :ref:`dealing-with-files`.

.. code-block:: python

	from pprint import pprint

	# List files on an acquisition
	acquisition = fw.get(acquisition_id)

	for f in acquisition.files:
	  print('Name: %s, type: %s' % (f.name, f.type))

	# Upload a file to an acquisition
	acquisition.upload_file('/path/to/file.txt')

	# Download a file to disk
	acquisition.download_file('file.txt', '/path/to/file.txt')

	# Files can also have metadata
	pprint(acquisition.files[0].info)

	acquisition.replace_file_info('file.txt', {'wordCount': 327})

File Classification
+++++++++++++++++++
Flywheel supports an extensible, multi-dimenstional classification scheme for files. Each dimension
of classification is referred to as an aspect. The available aspects are determined by the file's
modality.

For example, the ``MR`` modality provides the ``Intent``, ``Measurement`` and ``Features`` aspects.
In addition, the ``Custom`` aspect is always available, regardless of modality.

.. code-block:: python

	from pprint import pprint

	# Display the aspects defined in the MR modality
	mr = fw.get_modality('MR')
	pprint(mr)

	# Replace a file's modality and classification
	acquisition.replace_file_classification('file.txt', {
		'Intent': ['Structural'],
		'Measurement': ['T2']
	}, modality='MR')

	# Update a file's Custom classification, without changing
	# existing values or modality
	acquisition.update_file_classification('file.txt', {
		'Custom': ['value1', 'value2']
	})

	# Delete 'value1' from Custom classification
	acquisition.delete_file_classification('file.txt', {
		'Custom': ['value1']
	})

Timestamps [NEW]
++++++++++++++++
Objects with timestamps and created/modified dates provide helper accessors
to get those dates in the local (system) timezone, as well as the original
timezone in the case of acquisition and session timestamps.

For example:

.. code-block:: python

	# Acquisition Timestamp (tz=UTC)
	print(acquisition.timestamp.isoformat())

	# Acquisition Timestamp (tz=Local Timezone)
	print(acquisition.local_timestamp.isoformat())

	# Acquisition Timestamp (tz=Original Timezone)
	print(session.original_timestamp.isoformat())

Age at Time of Session [NEW]
++++++++++++++++++++++++++++
Sessions have a field for subject age at the time of the session,
in seconds. There are also helper accessors to get age in years,
months, weeks and days.

For example:

.. code-block:: python

	# Subject age in seconds
	print('Subject was {} seconds old', session.age)

	# Subject age in years
	print('Subject was {} years old', session.age_years)
