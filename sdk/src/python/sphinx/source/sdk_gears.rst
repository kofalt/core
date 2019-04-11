SDK Gears [NEW]
***************
This page shows examples of writing a gear using the SDK.

A pre-requisite for using this portion of the SDK is reading the
`Flywheel gear spec <https://github.com/flywheel-io/gears/tree/master/spec>`_, and understanding
how the configuration is structured, especially with inputs and configuration values.

The :class:`flywheel.gear_context.GearContext` class provides a simplified interface for performing common tasks
in the lifecycle of a gear, such as accessing input files, configuration values, logging messages,
accessing the SDK client and writing to the output folder.


Setup
=====
The first step of using this interface is to create an instance of the GearContext class and,
if desired, initialize logging. You can also print your configuration to the log to
make troubleshooting easier during development:

.. code-block:: python

   import flywheel
   with flywheel.GearContext() as context:
      # Setup basic logging
      context.init_logging()

      # Log the configuration for this job
      context.log_config()


Accessing Config
================
Once initialized, the job configuration is accessible as a regular python ``dict`` from the context:

.. code-block:: python

   # Get the configured speed, with a default of 2
   my_speed = context.config.get('speed', 2)


Accessing Inputs
================
You can get the full path to a named input file, or open the file directly:

.. code-block:: python

   # Get the path to the input file named 'dicom'
   dicom_path = context.get_input_path('dicom')

   # Open the dicom file for reading
   with context.open_input('dicom', 'rb') as dicom_file:
      dicom_data = dicom_file.read()

If you have context inputs, you can get their values directly:

.. code-block:: python

   # Get the FSL license context value
   fsl_license = context.get_context_value('fsl_license')
   if fsl_license is None:
      raise RuntimeError('No license found!')


Accessing the SDK Client
========================
If your gear is an SDK gear (that is, it has an api-key input), you can easily access
an instance of the Flywheel SDK Client:

.. code-block:: python

   # Lookup a project using the client
   project = context.client.lookup('my_group/Project 1')


Downloading BIDS
================
If your project or session is fully curated for BIDS, you can download all or a portion
of the project or session to a working directory in BIDS layout.

.. code-block:: python

   # Download all files from the session in BIDS format
   # bids_path will point to the BIDS folder
   bids_path = context.download_session_bids()

   # Download anat and func files from the project in BIDS format
   # bids_path will point to the BIDS folder
   bids_path = context.download_project_bids(folders=['anat', 'func'])


Writing Outputs
===============
The path to the output directory is available as a variable on the context, and
helper methods exist for opening an output file for writing:

.. code-block:: python

   print('Output path: {}'.format(context.output_dir))

   # Open an output file for writing
   with context.open_output('out-file.dcm', 'wb') as f:
      f.write(dicom_data)


Writing Metadata
================
Occasionally it's useful to add or update metadata on the destination, one of the
parent containers, or files on the destination (including output files)

This can be done using the metadata helper functions. The metadata will be written either
when ``write_metadata()`` is called, or the context is exited (if using a ``with`` statement)

.. code-block:: python

   # Metadata will be written at exit of the "with" block,
   # unless an exception occurs
   with flywheel.GearContext() as context:
      # Update the session label
      context.update_container_metadata('session', label='Session 1')

      # Update the destination (e.g. acquisition) label and timestamp
      updates = {
         'label': 'fMRI_Ret_bars',
         'timestamp': '2014-05-07T08:50:07+00:00'
      }
      context.update_destination_metadata(updates)

      # Set the modality and classification of an output file
      context.update_file_metadata('out-file.dcm', modality='MR', classification={
         'Intent': ['Functional'],
         'Measurement': ['T2*']
      })
