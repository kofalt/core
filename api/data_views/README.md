# Data Views

The idea of a data view is to provide a flattened aggregation of container fields (and possibly file data).

Data Views can operate on projects, sessions, subjects, acquisitions, analyses and files. Currently json, csv and tsv files are supported,
and can be extracted from gzip or zip files. They can produce:

- JSON as rows of objects
- JSON as a list of columns and a list of rows
- CSV
- TSV

Data Views are described via a specification object that includes columns to extract, what containers and files to match, 
and how to handle missing values. They can be saved for a user, group, project or site and can be executed against any container 
in the hierarchy.

## Data View Pipeline

At the core of the data view implementation is a configurable pipeline that consists of the following stages:
- [Aggregate](pipeline/aggregate.py) - This stage is always performed, and does the initial retrieval of containers
- [Match Analyses](pipeline/match_containers.py) - This stage is only performed if file retrieval from analyses is being performed.
	This filters the analyses retrieved in the aggregate stage, then produces one row per analysis.
- [Match Files](pipeline/match_containers.py) - This stage is only performed if file retrieval is being performed.
	It filters the file list retrieved in the aggregate stage, then produces one row per matched file.
- [Log Access](pipeline/log_access.py) - This stage adds entries to the access log for each container that will be accessed.
- [Read File](pipeline/read_file.py) - This stage is only performed if a file retrieval is planned. It will read
	each matched file and produce rows for each row found in the file.
- [Extract Columns](pipeline/extract_columns.py) - This stage is always performed. It flattens each row by extracting and
	optionally converting column values.
- [Missing Data Handler](pipeline/missing_data_strategies.py) - This stage is always performed. Depending on configuration
	it will either discard rows or replace missing values with some default.
- [Write](pipeline/write.py) - This stage is always performed, and is the terminal stage. It writes the flattened rows
	in the configured output format.

## Example Pipelines

### Aggregate Containers Only
```
+-----------+   +------------+   +-----------------+   +---------------------+   +-------+
| Aggregate +---> Log Access +---> Extract Columns +---> Handle Missing Data +---> Write |
+-----------+   +------------+   +-----------------+   +---------------------+   +-------+
```

### Aggregate with Files
```
+-----------+     +-------------+     +------------+     +-----------+
| Aggregate +-----> Match Files +-----> Log Access +-----> Read File |
+-----------+     +-------------+     +------------+     +-----+-----+
                                                               |    
            +-------+    +---------------------+   +-----------v-----+
            | Write <----+ Handle Missing Data <---+ Extract Columns |
            +-------+    +---------------------+   +-----------------+
```

### Aggregate with Analyses and Files
```
+-----------+     +----------------+    +-------------+     +------------+
| Aggregate +-----> Match Analyses +----> Match Files +-----> Log Access |
+-----------+     +----------------+    +-------------+     +------+-----+
                                                                   |
+-------+    +---------------------+   +-----------------+   +-----v-----+
| Write <----+ Handle Missing Data <---+ Extract Columns <---+ Read File |
+-------+    +---------------------+   +-----------------+   +-----------+
```


## Code Organization

- **data_views/** 
  - **pipeline/** - This module contains the pipeline stages for data view (described above). 
	Some of the stages have dependencies on modules in the `data_views` folder.
  - [**access_logger.py**](access_logger.py) - Provides a class for collecting then bulk creating access log entries.
  - [**config.py**](config.py) - Provides the DataViewConfig class which holds the configuration for data view execution.
  - [**data_view.py**](data_view.py) - The master DataView class which can take a view configuration and container id and execute a view.
  - [**file_opener.py**](file_opener.py) - Class that can take a file entry, and open and extract gz and zip files.
  - [**formatters.py**](formatters.py) - Contains formatting strategies for outputting row data.
  - [**handlers.py**](handlers.py) - API Endpoint handlers for data views
  - [**hierarchy_aggregator.py**](hierarchy_aggregator.py) - Helper class for performing database aggregation queries.
  - [**readers.py**](readers.py) - Contains file reading strategies for various file types.
  - [**util.py**](util.py) - Provides utility functions for filtering containers and extracting column values.
