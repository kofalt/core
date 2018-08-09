Flywheel Views
**************

Introduction
------------

Often times it is useful to get attributes across a large number of objects in the Flywheel hierarchy.
One possible way of retrieving fields in such a manner would be looping over each level in the hierarchy, 
collecting the desired fields at each level. This is problematic because it is tedious to write and inefficient 
to execute.

A view is an abstraction that describes how to collect and aggregate data on a Flywheel instance. 
Views are defined as a set of columns to collect and are executed against a container (such as a project, subject or session).
In addition, tabular or JSON file data may be aggregated from files, even files that are members of archives, or part of analysis output.

Data views provide an alternative way to efficiently aggregate data across the hierarchy in a tabular way, producing
results like this:

+---------------+-------------+-------------+--------------------+------------+---------------+----------+
| project.label | subject.age | subject.sex | acquisition.label  | trial_type | response_time | accuracy |
+===============+=============+=============+====================+============+===============+==========+ 
| color study   | 1040688000  | male        | task-redBlue       | go         | 1.435         | 1        |
+---------------+-------------+-------------+--------------------+------------+---------------+----------+
| color study   | 1040688000  | male        | task-redBlue       | stop       | 1.739         | 0        |
+---------------+-------------+-------------+--------------------+------------+---------------+----------+
| color study   | 851472000   | female      | task-redBlue       | go         | 1.379         | 1        |
+---------------+-------------+-------------+--------------------+------------+---------------+----------+
| color study   | 851472000   | female      | task-redBlue       | stop       | 1.534         | 1        |
+---------------+-------------+-------------+--------------------+------------+---------------+----------+

Creating A View
---------------

Views can be created using the :class:`~flywheel.ViewBuilder` class, or the short-hand :meth:`~flywheel.Flywheel.View` method. 
At a minimum, one column or file must be specified when creating a data view. A simple example would be to create a view that collects all of the built-in subject columns:

.. code-block:: matlab

    % Build a data view
    view = fw.View('columns', {{'subject'}})

Executing A View
----------------

A View object doesn't become useful until you execute it against a container. View results can be loaded directly into memory, or saved to a file. 
View results can also be loaded directly into a struct array, or a table.
Finally, you can also save the results of a view execution directly to a container as a file.

Load Struct View
++++++++++++++++

.. code-block:: matlab

    response = fw.readViewStruct(view, projectId);

Load Table View
+++++++++++++++

.. code-block:: matlab

    df = fw.readViewTable(view, projectId);

Save DataFrame to Local CSV
+++++++++++++++++++++++++++

.. code-block:: matlab

    fw.saveViewData(view, projectId, '/tmp/results.csv', 'format', 'csv');

Data Formats
------------

The following output formats are supported:

* json - The default format. Results will be returned as an array of objects, one per row.
* json-row-column - A second json format where columns are separate from rows, and rows is an array of arrays.
* json-flat - Similar to json, except that instead of an object, the rows are the top level array.
* csv - Comma-separated values format
* tsv - Tab-separated values format

Data format can be specified on any of the data view execution functions.

Columns
-------

Data view columns are references to container fields in the form of ``<container>.<field>``.

A current list of pre-defined columns and groups of columns is available via the :meth:`~flywheel.Flywheel.printViewColumns` method.
For example:

.. code-block:: text

    project (group): All column aliases belonging to project
    project.id (string): The project id
    project.label (string): The project label
    project.info (string): The freeform project metadata
    subject (group): All column aliases belonging to subject
    subject.id (string): The subject id
    subject.label (string): The subject label or code
    subject.firstname (string): The subject first name
    subject.lastname (string): The subject last name
    subject.age (int): The subject age, in seconds
    subject.info (string): The freeform subject metadata
    ...

Adding the ``project`` group column will result in ``project.id`` and ``project.label`` being added. Likewise adding the ``subject`` group column 
will result in the subject ``id``, ``label``, ``firstname``, ``lastname``, ``age`` (and more) columns being added to the view.

Info Columns
++++++++++++

The ``info`` columns are unique in that they represent the unstructured metadata associated with a container. As such, they are not included in 
the column groups, and behave a little bit differently. If the output data format is CSV or TSV, then a set of columns are extracted from the first
row encountered, which is generally the first object created. This may result in unexpected behavior if info fields are not uniform across each 
object. It's better in most cases to explicitly state which info fields you wish as columns: e.g. ``subject.info.IQ``.

Files
-----

Rows can also be extracted from CSV, TSV and JSON files that are present on the Flywheel instance. This can be done with the view builder by
specifying which ``container`` type to find files on and a ``filename`` wildcard match. In addition, analysis files can be matched by specifying
``analysisLabel``, ``analysisGearName`` and/or ``analysisGearVersion``.

For example:

.. code-block:: matlab

    % Read all columns from files named behavioral_results_*.csv on each session
    view = fw.View('container', 'session', 'filename', 'behavioral_results*.csv');

    % Read Mean_Diffusivity.csv results from the newest AFQ analyses on each session, and include session and subject labels
    builder = flywheel.ViewBuilder('columns', { {'subject.label'}, {'session.label'} },...
        'container', 'session', 'analysisGearName', 'afq', 'filename', 'Mean_Diffusivity.csv');
    builder.fileMatch('newest');
    builder.fileColumn('Left_Thalamic_Radiation', 'LTR', 'type', 'float');
    builder.fileColumn('Right_Thalamic_Radiation', 'RTR', 'type', 'float');
    view = builder.build();

Saving Views
------------

View definitions can be saved to your user account, or any project you have access to. For example:
    
.. code-block:: matlab

    me = fw.getCurrentUser().id;
    subjectsView = fw.View('label', 'Subject Info', 'columns', {{'subject'}});
    viewId = fw.addView(me, subjectsView);

Then you can execute the view any time against any container

.. code-block:: matlab

    df = fw.readViewTable(viewId, projectId)
