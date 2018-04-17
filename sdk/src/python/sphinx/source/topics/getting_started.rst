Getting Started with Flywheel SDK
*********************************

Introduction
------------
The Flywheel SDK is a python toolbox that provides programmatic 
access to the Flywheel API endpoints.

License
-------
Flywheel SDK has an MIT-based `license <https://github.com/flywheel-io/core/blob/master/LICENSE>`_.

Installation
------------
The latest python package can be installed using pip:

.. code-block:: bash

	pip install flywheel-sdk

The python wheel can also be downloaded from the `Releases Page <https://github.com/flywheel-io/core/releases>`_.

API Key
-------
The SDK requires an API key. You can find and generate your key on the Flywheel profile page. It will look like this:

.. image:: //core/static/images/api-key.png

Making API Calls
----------------
In order to make API calls, you will need to create an instance of the Flywheel client:

.. code-block:: python
	# import flywheel package
	import flywheel

	# Create client
	fw = flywheel.Flywheel('my-key')

Once you have a client instance, you can interact with the system. For instance, you could get information about yourself:

.. code-block:: python

	self = fw.get_current_user()
	print('I am %s %s' % (self.firstname, self.lastname))

Dealing with Files
------------------
Often times you'll find yourself wanting to upload or download file data to one of Flywheel's containers. When uploading,
you can either specify the path to the input file, or you can specify some in-memory data to upload using the FileSpec object.

.. code-block:: python

	# Upload the file at /tmp/hello.txt
	fw.upload_file_to_project(project_id, '/tmp/hello.txt')

	# Upload the data 'Hello World!'
	file_spec = flywheel.FileSpec('hello.txt', 'Hello World!\n', 'text/plain')
	fw.upload_file_to_project(project_id, file_spec)

When downloading, you specify the destination file, or you can download directly to memory

.. code-block:: python

	# Download file to /tmp/hello.txt
	fw.download_file_from_project(project_id, 'hello.txt', '/tmp/hello.txt')

	# Download file contents directly to memory
	data = fw.download_file_from_project_as_data(project_id, 'hello.txt')
