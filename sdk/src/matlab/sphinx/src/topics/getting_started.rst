Getting Started with Flywheel SDK
*********************************

Introduction
------------
The Flywheel SDK is a matlab toolbox that provides programmatic 
access to the Flywheel API endpoints.

License
-------
Flywheel SDK has an MIT-based `license <https://github.com/flywheel-io/core/blob/master/LICENSE>`_.

Installation
------------
The latest Matlab Toolbox can be downloaded from the `Releases Page <https://github.com/flywheel-io/core/releases>`_.
Installation can be done one of two ways, depending on your Operating System. For OSX and Windows you should be able 
to double-click the downloaded toolbox in order to perform the installation.

If your Operating System does not support double-click installation of toolboxes, you can install from within the matlab console.

.. code-block:: matlab

	toolboxFile = '/path/to/flywheel-sdk-version.mltbx';
	installedToolbox = matlab.addons.toolbox.installToolbox(toolboxFile)

API Key
-------
The SDK requires an API key. You can find and generate your key on the Flywheel profile page. It will look like this:

.. image:: //core/static/images/api-key.png

Making API Calls
----------------
In order to make API calls, you will need to create an instance of the Flywheel client:

.. code-block:: matlab

	% Create client
	fw = flywheel.Flywheel('my-key')

Once you have a client instance, you can interact with the system. For instance, you could get information about yourself:

.. code-block:: matlab

	self = fw.getCurrentUser();
	fprintf('I am %s %s\n', self.firstname, self.lastname);

Getting Help
------------
You can query the client or objects returned by api calls for additional information:

.. code-block:: matlab

	help(fw); % Display available functions
	disp(self); % Print the properties in the 'self' object

Dealing with Files
------------------
Often times you'll find yourself wanting to upload or download file data to one of Flywheel's containers. When uploading,
you can either specify the path to the input file, or you can specify some in-memory data to upload using the FileSpec object.

.. code-block:: matlab

	% Upload the file at /tmp/hello.txt
	fw.uploadFileToProject(projectId, '/tmp/hello.txt');

	% Upload the data 'Hello World!'
	fileSpec = flywheel.FileSpec('hello.txt', 'Hello World!\n', 'text/plain');
	fw.uploadFileToProject(projectId, fileSpec);

When downloading, you specify the destination file:

.. code-block:: matlab

	% Download file to /tmp/hello.txt
	fw.downloadFileFromProject(projectId, 'hello.txt', '/tmp/hello.txt');
