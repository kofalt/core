Data Views
**********

Introduction
------------

Often times it is useful to get attributes across a large number of objects in the flywheel hierarchy.
One possible way of retrieving fields in such a manner would be looping over each level in the hierarchy, 
collecting the desired fields at each level. This is problematic because it is tedious to write and inefficient 
to execute.

Data views provide an alternative way to efficiently aggregate data across the hierarchy in a tabular way, producing
results like:

+-------------+-------------+-------------+--------------------+------------+---------------+----------+
| project     | subject_age | subject_sex | acquisition        | trial_type | response_time | accuracy |
+=============+=============+=============+====================+============+===============+==========+ 
| color study | 1040688000  | male        | task-redBlue       | go         | 1.435         | 1        |
+-------------+-------------+-------------+--------------------+------------+---------------+----------+
| color study | 1040688000  | male        | task-redBlue       | stop       | 1.739         | 0        |
+-------------+-------------+-------------+--------------------+------------+---------------+----------+
| color study | 851472000   | female      | task-redBlue       | go         | 1.379         | 1        |
+-------------+-------------+-------------+--------------------+------------+---------------+----------+
| color study | 851472000   | female      | task-redBlue       | stop       | 1.534         | 1        |
+-------------+-------------+-------------+--------------------+------------+---------------+----------+


Declaration
-----------

Data views are defined as a set of columns to collect and are executed against a container (such as a project, subject or session).
In addition, tabular or JSON file data may be aggregated from files, even files that are members of archives.

Declaring columns from object metadata is done as follows:

.. code-block:: python

	columns = [
		{ 'src': 'project.label', 'dst': 'project' },
		{ 'src': 'subject.age', 'dst': 'subject_age' },
		{ 'src': 'subject.sex', 'dst': 'subject_sex' }
	]

Extracting data from files relies on specifying a container and a filename, and optionally another set of columns.

.. code-block:: python

	file_columns = [
		{ 'src': 'trial_type' },
		{ 'src': 'response_time' },
		{ 'src': 'acc', 'dst': 'accuracy' }
	]
	file_spec = {
		'container': 'acquisition',
		'filter': { 'value': 'events.tsv' },
		'columns': file_columns
	}

To create the full view object, and execute it against a project with and id of: 

.. code-block:: python

	results = fw.execute_adhoc_data_view('5ae8b625f3b83d287a2026d6', {
		'columns': columns,
		'fileSpec': file_spec
	})

Saving Views
------------

Views can be saved to your user account, or any project you have access to. For example:
	
.. code-block:: python

	viewId = fw.add_data_view({
		'label': 'Color Study Response By Subject',
		'columns': columns,
		'fileSpec': file_spec
	})

Then you can execute the view any time against any container

.. code-block:: python

	results = fw.download_data_view(viewId, '5ae8b625f3b83d287a2026d6')


