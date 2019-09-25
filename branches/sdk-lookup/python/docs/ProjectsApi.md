# flywheel.ProjectsApi

All URIs are relative to *https://dev.flywheel.io/api*

Method | HTTP request | Description
------------- | ------------- | -------------
[**add_project**](ProjectsApi.md#add_project) | **POST** /projects | Create a new project
[**add_project_analysis**](ProjectsApi.md#add_project_analysis) | **POST** /projects/{ProjectId}/analyses | Create an analysis and upload files.
[**add_project_analysis_note**](ProjectsApi.md#add_project_analysis_note) | **POST** /projects/{ProjectId}/analyses/{AnalysisId}/notes | Add a note to project analysis.
[**add_project_note**](ProjectsApi.md#add_project_note) | **POST** /projects/{ProjectId}/notes | Add a note to project.
[**add_project_permission**](ProjectsApi.md#add_project_permission) | **POST** /projects/{ProjectId}/permissions | Add a permission
[**add_project_rule**](ProjectsApi.md#add_project_rule) | **POST** /projects/{ProjectId}/rules | Create a new rule for a project.
[**add_project_tag**](ProjectsApi.md#add_project_tag) | **POST** /projects/{ProjectId}/tags | Add a tag to project.
[**delete_project**](ProjectsApi.md#delete_project) | **DELETE** /projects/{ProjectId} | Delete a project
[**delete_project_analysis**](ProjectsApi.md#delete_project_analysis) | **DELETE** /projects/{ProjectId}/analyses/{AnalysisId} | Delete an anaylsis
[**delete_project_analysis_note**](ProjectsApi.md#delete_project_analysis_note) | **DELETE** /projects/{ProjectId}/analyses/{AnalysisId}/notes/{NoteId} | Remove a note from project analysis.
[**delete_project_file**](ProjectsApi.md#delete_project_file) | **DELETE** /projects/{ProjectId}/files/{FileName} | Delete a file
[**delete_project_note**](ProjectsApi.md#delete_project_note) | **DELETE** /projects/{ProjectId}/notes/{NoteId} | Remove a note from project
[**delete_project_tag**](ProjectsApi.md#delete_project_tag) | **DELETE** /projects/{ProjectId}/tags/{TagValue} | Delete a tag
[**delete_project_user_permission**](ProjectsApi.md#delete_project_user_permission) | **DELETE** /projects/{ProjectId}/permissions/{UserId} | Delete a permission
[**download_file_from_project**](ProjectsApi.md#download_file_from_project) | **GET** /projects/{ProjectId}/files/{FileName} | Download a file.
[**get_project_download_ticket**](ProjectsApi.md#get_project_download_ticket) | **GET** /projects/{ProjectId}/files/{FileName} | Download a file.
[**download_project_analysis_inputs**](ProjectsApi.md#download_project_analysis_inputs) | **GET** /projects/{ProjectId}/analyses/{AnalysisId}/inputs | Download analysis inputs.
[**download_project_analysis_inputs_by_filename**](ProjectsApi.md#download_project_analysis_inputs_by_filename) | **GET** /projects/{ProjectId}/analyses/{AnalysisId}/inputs/{Filename} | Download anaylsis inputs with filter.
[**download_project_analysis_outputs**](ProjectsApi.md#download_project_analysis_outputs) | **GET** /projects/{ProjectId}/analyses/{AnalysisId}/files | Download analysis outputs.
[**download_project_analysis_outputs_by_filename**](ProjectsApi.md#download_project_analysis_outputs_by_filename) | **GET** /projects/{ProjectId}/analyses/{AnalysisId}/files/{Filename} | Download anaylsis outputs with filter.
[**end_project_packfile_upload**](ProjectsApi.md#end_project_packfile_upload) | **GET** /projects/{ProjectId}/packfile-end | End a packfile upload
[**get_all_projects**](ProjectsApi.md#get_all_projects) | **GET** /projects | Get a list of projects
[**get_all_projects_groups**](ProjectsApi.md#get_all_projects_groups) | **GET** /projects/groups | List all groups which have a project in them
[**get_project**](ProjectsApi.md#get_project) | **GET** /projects/{ProjectId} | Get a single project
[**get_project_acquisitions**](ProjectsApi.md#get_project_acquisitions) | **GET** /projects/{ProjectId}/acquisitions | List all acquisitions for the given project.
[**get_project_analyses**](ProjectsApi.md#get_project_analyses) | **GET** /projects/{ProjectId}/analyses | Get analyses for project.
[**get_project_analysis**](ProjectsApi.md#get_project_analysis) | **GET** /projects/{ProjectId}/analyses/{AnalysisId} | Get an analysis.
[**get_project_file_info**](ProjectsApi.md#get_project_file_info) | **GET** /projects/{ProjectId}/files/{FileName}/info | Get info for a particular file.
[**get_project_note**](ProjectsApi.md#get_project_note) | **GET** /projects/{ProjectId}/notes/{NoteId} | Get a note on project.
[**get_project_rule**](ProjectsApi.md#get_project_rule) | **GET** /projects/{ProjectId}/rules/{RuleId} | Get a project rule.
[**get_project_rules**](ProjectsApi.md#get_project_rules) | **GET** /projects/{ProjectId}/rules | List all rules for a project.
[**get_project_sessions**](ProjectsApi.md#get_project_sessions) | **GET** /projects/{ProjectId}/sessions | List all sessions for the given project.
[**get_project_tag**](ProjectsApi.md#get_project_tag) | **GET** /projects/{ProjectId}/tags/{TagValue} | Get the value of a tag, by name.
[**get_project_user_permission**](ProjectsApi.md#get_project_user_permission) | **GET** /projects/{ProjectId}/permissions/{UserId} | List a user&#39;s permissions for this project.
[**modify_project**](ProjectsApi.md#modify_project) | **PUT** /projects/{ProjectId} | Update a project
[**modify_project_file**](ProjectsApi.md#modify_project_file) | **PUT** /projects/{ProjectId}/files/{FileName} | Modify a file&#39;s attributes
[**modify_project_file_info**](ProjectsApi.md#modify_project_file_info) | **POST** /projects/{ProjectId}/files/{FileName}/info | Update info for a particular file.
[**modify_project_info**](ProjectsApi.md#modify_project_info) | **POST** /projects/{ProjectId}/info | Update or replace info for a project.
[**modify_project_note**](ProjectsApi.md#modify_project_note) | **PUT** /projects/{ProjectId}/notes/{NoteId} | Update a note on project.
[**modify_project_rule**](ProjectsApi.md#modify_project_rule) | **PUT** /projects/{ProjectId}/rules/{RuleId} | Update a rule on a project.
[**modify_project_user_permission**](ProjectsApi.md#modify_project_user_permission) | **PUT** /projects/{ProjectId}/permissions/{UserId} | Update a user&#39;s permission for this project.
[**project_packfile_upload**](ProjectsApi.md#project_packfile_upload) | **POST** /projects/{ProjectId}/packfile | Add files to an in-progress packfile
[**recalc_all_projects**](ProjectsApi.md#recalc_all_projects) | **POST** /projects/recalc | Recalculate all sessions against their project templates.
[**recalc_project**](ProjectsApi.md#recalc_project) | **POST** /projects/{ProjectId}/recalc | Recalculate if sessions in the project satisfy the template.
[**remove_project_rule**](ProjectsApi.md#remove_project_rule) | **DELETE** /projects/{ProjectId}/rules/{RuleId} | Remove a project rule.
[**remove_project_template**](ProjectsApi.md#remove_project_template) | **DELETE** /projects/{ProjectId}/template | Remove the session template for a project.
[**rename_project_tag**](ProjectsApi.md#rename_project_tag) | **PUT** /projects/{ProjectId}/tags/{TagValue} | Rename a tag.
[**replace_project_file**](ProjectsApi.md#replace_project_file) | **POST** /projects/{ProjectId}/files/{FileName} | Replace a file
[**set_project_template**](ProjectsApi.md#set_project_template) | **POST** /projects/{ProjectId}/template | Set the session template for a project.
[**start_project_packfile_upload**](ProjectsApi.md#start_project_packfile_upload) | **POST** /projects/{ProjectId}/packfile-start | Start a packfile upload to project
[**upload_file_to_project**](ProjectsApi.md#upload_file_to_project) | **POST** /projects/{ProjectId}/files | Upload a file to project.


# **add_project**
> ContainerNewOutput add_project(body)

Create a new project

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
body = flywheel.Project() # Project | 

try:
    # Create a new project
    api_response = api_instance.add_project(body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->add_project: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **body** | [**Project**](Project.md)|  | 

### Return type

[**ContainerNewOutput**](ContainerNewOutput.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **add_project_analysis**
> ContainerNewOutput add_project_analysis(project_id, body, job=job)

Create an analysis and upload files.

When query param \"job\" is \"true\", send JSON to create an analysis and job.  Otherwise, multipart/form-data to upload files and create an analysis. 

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
body = flywheel.AnalysisInputAny() # AnalysisInputAny | 
job = true # bool | Return job as an object instead of an id (optional)

try:
    # Create an analysis and upload files.
    api_response = api_instance.add_project_analysis(project_id, body, job=job)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->add_project_analysis: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **body** | [**AnalysisInputAny**](AnalysisInputAny.md)|  | 
 **job** | **bool**| Return job as an object instead of an id | [optional] 

### Return type

[**ContainerNewOutput**](ContainerNewOutput.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **add_project_analysis_note**
> InlineResponse2001 add_project_analysis_note(project_id, analysis_id, body)

Add a note to project analysis.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
analysis_id = 'analysis_id_example' # str | 
body = flywheel.Note() # Note | 

try:
    # Add a note to project analysis.
    api_response = api_instance.add_project_analysis_note(project_id, analysis_id, body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->add_project_analysis_note: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **analysis_id** | **str**|  | 
 **body** | [**Note**](Note.md)|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **add_project_note**
> InlineResponse2001 add_project_note(project_id, body)

Add a note to project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
body = flywheel.Note() # Note | 

try:
    # Add a note to project.
    api_response = api_instance.add_project_note(project_id, body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->add_project_note: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **body** | [**Note**](Note.md)|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **add_project_permission**
> InlineResponse2001 add_project_permission(project_id, body=body)

Add a permission

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
body = flywheel.Permission() # Permission |  (optional)

try:
    # Add a permission
    api_response = api_instance.add_project_permission(project_id, body=body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->add_project_permission: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **body** | [**Permission**](Permission.md)|  | [optional] 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **add_project_rule**
> add_project_rule(project_id, body=body)

Create a new rule for a project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
body = flywheel.Rule() # Rule |  (optional)

try:
    # Create a new rule for a project.
    api_instance.add_project_rule(project_id, body=body)
except ApiException as e:
    print("Exception when calling ProjectsApi->add_project_rule: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **body** | [**Rule**](Rule.md)|  | [optional] 

### Return type

void (empty response body)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **add_project_tag**
> InlineResponse2001 add_project_tag(project_id, body)

Add a tag to project.

Progates changes to projects, sessions and acquisitions

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
body = flywheel.Tag() # Tag | 

try:
    # Add a tag to project.
    api_response = api_instance.add_project_tag(project_id, body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->add_project_tag: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **body** | [**Tag**](Tag.md)|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_project**
> InlineResponse200 delete_project(project_id)

Delete a project

Only site admins and users with \"admin\" project permissions may delete a project

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 

try:
    # Delete a project
    api_response = api_instance.delete_project(project_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->delete_project: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 

### Return type

[**InlineResponse200**](InlineResponse200.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_project_analysis**
> InlineResponse200 delete_project_analysis(project_id, analysis_id)

Delete an anaylsis

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
analysis_id = 'analysis_id_example' # str | 

try:
    # Delete an anaylsis
    api_response = api_instance.delete_project_analysis(project_id, analysis_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->delete_project_analysis: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **analysis_id** | **str**|  | 

### Return type

[**InlineResponse200**](InlineResponse200.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_project_analysis_note**
> InlineResponse2001 delete_project_analysis_note(project_id, analysis_id, note_id)

Remove a note from project analysis.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
analysis_id = 'analysis_id_example' # str | 
note_id = 'note_id_example' # str | 

try:
    # Remove a note from project analysis.
    api_response = api_instance.delete_project_analysis_note(project_id, analysis_id, note_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->delete_project_analysis_note: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **analysis_id** | **str**|  | 
 **note_id** | **str**|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_project_file**
> InlineResponse2001 delete_project_file(project_id, file_name)

Delete a file

A user with read-write or higher permissions on the container may delete files that were uploaded by users or were the output of jobs. (Specifically, files whose `origin.type` is either `job` or `user`.) <br/> A user with admin permissions on the container may delete any file. 

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
file_name = 'file_name_example' # str | 

try:
    # Delete a file
    api_response = api_instance.delete_project_file(project_id, file_name)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->delete_project_file: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **file_name** | **str**|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_project_note**
> InlineResponse2001 delete_project_note(project_id, note_id)

Remove a note from project

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
note_id = 'note_id_example' # str | 

try:
    # Remove a note from project
    api_response = api_instance.delete_project_note(project_id, note_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->delete_project_note: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **note_id** | **str**|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_project_tag**
> InlineResponse2001 delete_project_tag(project_id, tag_value)

Delete a tag

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
tag_value = 'tag_value_example' # str | The tag to interact with

try:
    # Delete a tag
    api_response = api_instance.delete_project_tag(project_id, tag_value)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->delete_project_tag: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **tag_value** | **str**| The tag to interact with | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_project_user_permission**
> InlineResponse2001 delete_project_user_permission(project_id, user_id)

Delete a permission

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
user_id = 'user_id_example' # str | 

try:
    # Delete a permission
    api_response = api_instance.delete_project_user_permission(project_id, user_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->delete_project_user_permission: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **user_id** | **str**|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **download_file_from_project**
> DownloadTicket download_file_from_project(project_id, file_name, view=view, info=info, member=member)

Download a file.

Files can be downloaded directly from this endpoint with a valid \"Authorization\" header or via a ticket id.  To generate a ticket:   - Make a request with an empty \"ticket\" parameter and a valid \"Authorization\" header. The server will respond with a generated ticket id.   - Make another request with the received ticket id in the \"ticket\" parameter. A valid \"Authorization\" header is no longer required.  When \"view\" is true, [RFC7233](https://tools.ietf.org/html/rfc7233) range request headers are supported. 

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
file_name = 'file_name_example' # str | 
view = false # bool | If true, the proper \"Content-Type\" header based on the file's mimetype is set on response If false, the \"Content-Type\" header is set to \"application/octet-stream\"  (optional) (default to false)
info = false # bool | If the file is a zipfile, return a json response of zipfile member information (optional) (default to false)
member = 'member_example' # str | The filename of a zipfile member to download rather than the entire file (optional)

try:
    # Download a file.
    api_response = api_instance.download_file_from_project(project_id, file_name, view=view, info=info, member=member)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->download_file_from_project: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **file_name** | **str**|  | 
 **view** | **bool**| If true, the proper \&quot;Content-Type\&quot; header based on the file&#39;s mimetype is set on response If false, the \&quot;Content-Type\&quot; header is set to \&quot;application/octet-stream\&quot;  | [optional] [default to false]
 **info** | **bool**| If the file is a zipfile, return a json response of zipfile member information | [optional] [default to false]
 **member** | **str**| The filename of a zipfile member to download rather than the entire file | [optional] 

### Return type

[**DownloadTicket**](DownloadTicket.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/octet-stream

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_download_ticket**
> DownloadTicket get_project_download_ticket(project_id, file_name, ticket=ticket, view=view, info=info, member=member)

Download a file.

Files can be downloaded directly from this endpoint with a valid \"Authorization\" header or via a ticket id.  To generate a ticket:   - Make a request with an empty \"ticket\" parameter and a valid \"Authorization\" header. The server will respond with a generated ticket id.   - Make another request with the received ticket id in the \"ticket\" parameter. A valid \"Authorization\" header is no longer required.  When \"view\" is true, [RFC7233](https://tools.ietf.org/html/rfc7233) range request headers are supported. 

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
file_name = 'file_name_example' # str | 
ticket = 'ticket_example' # str | The generated ticket id for the download, or present but empty to generate a ticket id (optional)
view = false # bool | If true, the proper \"Content-Type\" header based on the file's mimetype is set on response If false, the \"Content-Type\" header is set to \"application/octet-stream\"  (optional) (default to false)
info = false # bool | If the file is a zipfile, return a json response of zipfile member information (optional) (default to false)
member = 'member_example' # str | The filename of a zipfile member to download rather than the entire file (optional)

try:
    # Download a file.
    api_response = api_instance.get_project_download_ticket(project_id, file_name, ticket=ticket, view=view, info=info, member=member)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_download_ticket: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **file_name** | **str**|  | 
 **ticket** | **str**| The generated ticket id for the download, or present but empty to generate a ticket id | [optional] 
 **view** | **bool**| If true, the proper \&quot;Content-Type\&quot; header based on the file&#39;s mimetype is set on response If false, the \&quot;Content-Type\&quot; header is set to \&quot;application/octet-stream\&quot;  | [optional] [default to false]
 **info** | **bool**| If the file is a zipfile, return a json response of zipfile member information | [optional] [default to false]
 **member** | **str**| The filename of a zipfile member to download rather than the entire file | [optional] 

### Return type

[**DownloadTicket**](DownloadTicket.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **download_project_analysis_inputs**
> AnalysisFilesCreateTicketOutput download_project_analysis_inputs(project_id, analysis_id, ticket=ticket)

Download analysis inputs.

If \"ticket\" query param is included and not empty, download inputs. If \"ticket\" query param is included and empty, create a ticket for all inputs in the anlaysis If no \"ticket\" query param is included, server error 500 

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
analysis_id = 'analysis_id_example' # str | 
ticket = 'ticket_example' # str | ticket id of the inputs to download (optional)

try:
    # Download analysis inputs.
    api_response = api_instance.download_project_analysis_inputs(project_id, analysis_id, ticket=ticket)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->download_project_analysis_inputs: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **analysis_id** | **str**|  | 
 **ticket** | **str**| ticket id of the inputs to download | [optional] 

### Return type

[**AnalysisFilesCreateTicketOutput**](AnalysisFilesCreateTicketOutput.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json, application/octet-stream

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **download_project_analysis_inputs_by_filename**
> AnalysisFilesCreateTicketOutput download_project_analysis_inputs_by_filename(project_id, analysis_id, filename, ticket=ticket)

Download anaylsis inputs with filter.

If \"ticket\" query param is included and not empty, download inputs. If \"ticket\" query param is included and empty, create a ticket for matching inputs in the anlaysis. If no \"ticket\" query param is included, inputs will be downloaded directly. 

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
analysis_id = 'analysis_id_example' # str | 
filename = 'filename_example' # str | regex to select inputs for download
ticket = 'ticket_example' # str | ticket id of the inputs to download (optional)

try:
    # Download anaylsis inputs with filter.
    api_response = api_instance.download_project_analysis_inputs_by_filename(project_id, analysis_id, filename, ticket=ticket)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->download_project_analysis_inputs_by_filename: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **analysis_id** | **str**|  | 
 **filename** | **str**| regex to select inputs for download | 
 **ticket** | **str**| ticket id of the inputs to download | [optional] 

### Return type

[**AnalysisFilesCreateTicketOutput**](AnalysisFilesCreateTicketOutput.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json, application/octet-stream

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **download_project_analysis_outputs**
> AnalysisFilesCreateTicketOutput download_project_analysis_outputs(project_id, analysis_id, ticket=ticket)

Download analysis outputs.

If \"ticket\" query param is included and not empty, download outputs. If \"ticket\" query param is included and empty, create a ticket for all outputs in the anlaysis If no \"ticket\" query param is included, server error 500 

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
analysis_id = 'analysis_id_example' # str | 
ticket = 'ticket_example' # str | ticket id of the outputs to download (optional)

try:
    # Download analysis outputs.
    api_response = api_instance.download_project_analysis_outputs(project_id, analysis_id, ticket=ticket)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->download_project_analysis_outputs: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **analysis_id** | **str**|  | 
 **ticket** | **str**| ticket id of the outputs to download | [optional] 

### Return type

[**AnalysisFilesCreateTicketOutput**](AnalysisFilesCreateTicketOutput.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json, application/octet-stream

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **download_project_analysis_outputs_by_filename**
> AnalysisFilesCreateTicketOutput download_project_analysis_outputs_by_filename(project_id, analysis_id, filename, ticket=ticket)

Download anaylsis outputs with filter.

If \"ticket\" query param is included and not empty, download outputs. If \"ticket\" query param is included and empty, create a ticket for matching outputs in the anlaysis. If no \"ticket\" query param is included, outputs will be downloaded directly. 

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
analysis_id = 'analysis_id_example' # str | 
filename = 'filename_example' # str | regex to select outputs for download
ticket = 'ticket_example' # str | ticket id of the outputs to download (optional)

try:
    # Download anaylsis outputs with filter.
    api_response = api_instance.download_project_analysis_outputs_by_filename(project_id, analysis_id, filename, ticket=ticket)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->download_project_analysis_outputs_by_filename: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **analysis_id** | **str**|  | 
 **filename** | **str**| regex to select outputs for download | 
 **ticket** | **str**| ticket id of the outputs to download | [optional] 

### Return type

[**AnalysisFilesCreateTicketOutput**](AnalysisFilesCreateTicketOutput.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json, application/octet-stream

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **end_project_packfile_upload**
> end_project_packfile_upload(project_id, token, metadata)

End a packfile upload

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
token = 'token_example' # str | 
metadata = 'metadata_example' # str | string-encoded metadata json object.

try:
    # End a packfile upload
    api_instance.end_project_packfile_upload(project_id, token, metadata)
except ApiException as e:
    print("Exception when calling ProjectsApi->end_project_packfile_upload: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **token** | **str**|  | 
 **metadata** | **str**| string-encoded metadata json object. | 

### Return type

void (empty response body)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: text/event-stream

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_all_projects**
> list[Project] get_all_projects()

Get a list of projects

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))

try:
    # Get a list of projects
    api_response = api_instance.get_all_projects()
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_all_projects: %s\n" % e)
```

### Parameters
This endpoint does not need any parameter.

### Return type

[**list[Project]**](Project.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_all_projects_groups**
> list[Group] get_all_projects_groups()

List all groups which have a project in them

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))

try:
    # List all groups which have a project in them
    api_response = api_instance.get_all_projects_groups()
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_all_projects_groups: %s\n" % e)
```

### Parameters
This endpoint does not need any parameter.

### Return type

[**list[Group]**](Group.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project**
> Project get_project(project_id)

Get a single project

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 

try:
    # Get a single project
    api_response = api_instance.get_project(project_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 

### Return type

[**Project**](Project.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_acquisitions**
> list[Acquisition] get_project_acquisitions(project_id)

List all acquisitions for the given project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 

try:
    # List all acquisitions for the given project.
    api_response = api_instance.get_project_acquisitions(project_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_acquisitions: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 

### Return type

[**list[Acquisition]**](Acquisition.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_analyses**
> list[AnalysisListEntry] get_project_analyses(project_id)

Get analyses for project.

Returns analyses that directly belong to this resource.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 

try:
    # Get analyses for project.
    api_response = api_instance.get_project_analyses(project_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_analyses: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 

### Return type

[**list[AnalysisListEntry]**](AnalysisListEntry.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_analysis**
> AnalysisOutput get_project_analysis(project_id, analysis_id, inflate_job=inflate_job)

Get an analysis.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
analysis_id = 'analysis_id_example' # str | 
inflate_job = true # bool | Return job as an object instead of an id (optional)

try:
    # Get an analysis.
    api_response = api_instance.get_project_analysis(project_id, analysis_id, inflate_job=inflate_job)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_analysis: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **analysis_id** | **str**|  | 
 **inflate_job** | **bool**| Return job as an object instead of an id | [optional] 

### Return type

[**AnalysisOutput**](AnalysisOutput.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_file_info**
> FileEntry get_project_file_info(project_id, file_name)

Get info for a particular file.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
file_name = 'file_name_example' # str | 

try:
    # Get info for a particular file.
    api_response = api_instance.get_project_file_info(project_id, file_name)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_file_info: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **file_name** | **str**|  | 

### Return type

[**FileEntry**](FileEntry.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_note**
> Note get_project_note(project_id, note_id)

Get a note on project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
note_id = 'note_id_example' # str | 

try:
    # Get a note on project.
    api_response = api_instance.get_project_note(project_id, note_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_note: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **note_id** | **str**|  | 

### Return type

[**Note**](Note.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_rule**
> Rule get_project_rule(project_id, rule_id)

Get a project rule.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
rule_id = 'rule_id_example' # str | 

try:
    # Get a project rule.
    api_response = api_instance.get_project_rule(project_id, rule_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_rule: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **rule_id** | **str**|  | 

### Return type

[**Rule**](Rule.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_rules**
> list[Rule] get_project_rules(project_id)

List all rules for a project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 

try:
    # List all rules for a project.
    api_response = api_instance.get_project_rules(project_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_rules: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 

### Return type

[**list[Rule]**](Rule.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_sessions**
> list[Session] get_project_sessions(project_id)

List all sessions for the given project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 

try:
    # List all sessions for the given project.
    api_response = api_instance.get_project_sessions(project_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_sessions: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 

### Return type

[**list[Session]**](Session.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_tag**
> Tag get_project_tag(project_id, tag_value)

Get the value of a tag, by name.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
tag_value = 'tag_value_example' # str | The tag to interact with

try:
    # Get the value of a tag, by name.
    api_response = api_instance.get_project_tag(project_id, tag_value)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_tag: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **tag_value** | **str**| The tag to interact with | 

### Return type

[**Tag**](Tag.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_project_user_permission**
> Permission get_project_user_permission(project_id, user_id)

List a user's permissions for this project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
user_id = 'user_id_example' # str | 

try:
    # List a user's permissions for this project.
    api_response = api_instance.get_project_user_permission(project_id, user_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->get_project_user_permission: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **user_id** | **str**|  | 

### Return type

[**Permission**](Permission.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **modify_project**
> InlineResponse2001 modify_project(project_id, body)

Update a project

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
body = flywheel.Project() # Project | 

try:
    # Update a project
    api_response = api_instance.modify_project(project_id, body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->modify_project: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **body** | [**Project**](Project.md)|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **modify_project_file**
> InlineResponse2003 modify_project_file(project_id, file_name, body)

Modify a file's attributes

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
file_name = 'file_name_example' # str | 
body = flywheel.FileEntry() # FileEntry | 

try:
    # Modify a file's attributes
    api_response = api_instance.modify_project_file(project_id, file_name, body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->modify_project_file: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **file_name** | **str**|  | 
 **body** | [**FileEntry**](FileEntry.md)|  | 

### Return type

[**InlineResponse2003**](InlineResponse2003.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **modify_project_file_info**
> InlineResponse2001 modify_project_file_info(project_id, file_name, body)

Update info for a particular file.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
file_name = 'file_name_example' # str | 
body = flywheel.InfoUpdateInput() # InfoUpdateInput | 

try:
    # Update info for a particular file.
    api_response = api_instance.modify_project_file_info(project_id, file_name, body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->modify_project_file_info: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **file_name** | **str**|  | 
 **body** | [**InfoUpdateInput**](InfoUpdateInput.md)|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **modify_project_info**
> modify_project_info(project_id, body)

Update or replace info for a project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
body = flywheel.InfoUpdateInput() # InfoUpdateInput | 

try:
    # Update or replace info for a project.
    api_instance.modify_project_info(project_id, body)
except ApiException as e:
    print("Exception when calling ProjectsApi->modify_project_info: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **body** | [**InfoUpdateInput**](InfoUpdateInput.md)|  | 

### Return type

void (empty response body)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **modify_project_note**
> InlineResponse2001 modify_project_note(project_id, note_id, body)

Update a note on project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
note_id = 'note_id_example' # str | 
body = flywheel.Note() # Note | 

try:
    # Update a note on project.
    api_response = api_instance.modify_project_note(project_id, note_id, body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->modify_project_note: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **note_id** | **str**|  | 
 **body** | [**Note**](Note.md)|  | 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **modify_project_rule**
> modify_project_rule(project_id, rule_id, body=body)

Update a rule on a project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
rule_id = 'rule_id_example' # str | 
body = flywheel.Rule() # Rule |  (optional)

try:
    # Update a rule on a project.
    api_instance.modify_project_rule(project_id, rule_id, body=body)
except ApiException as e:
    print("Exception when calling ProjectsApi->modify_project_rule: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **rule_id** | **str**|  | 
 **body** | [**Rule**](Rule.md)|  | [optional] 

### Return type

void (empty response body)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **modify_project_user_permission**
> InlineResponse2001 modify_project_user_permission(project_id, user_id, body=body)

Update a user's permission for this project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
user_id = 'user_id_example' # str | 
body = flywheel.Permission() # Permission |  (optional)

try:
    # Update a user's permission for this project.
    api_response = api_instance.modify_project_user_permission(project_id, user_id, body=body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->modify_project_user_permission: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **user_id** | **str**|  | 
 **body** | [**Permission**](Permission.md)|  | [optional] 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **project_packfile_upload**
> list[FileEntry] project_packfile_upload(project_id, token, file)

Add files to an in-progress packfile

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
token = 'token_example' # str | 
file = '/path/to/file.txt' # file | 

try:
    # Add files to an in-progress packfile
    api_response = api_instance.project_packfile_upload(project_id, token, file)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->project_packfile_upload: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **token** | **str**|  | 
 **file** | **file**|  | 

### Return type

[**list[FileEntry]**](FileEntry.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: multipart/form-data
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **recalc_all_projects**
> SessionTemplateRecalcOutput recalc_all_projects()

Recalculate all sessions against their project templates.

Iterates all projects that have a session template. Recalculate if projects' sessions satisfy the template. Returns list of modified session ids. 

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))

try:
    # Recalculate all sessions against their project templates.
    api_response = api_instance.recalc_all_projects()
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->recalc_all_projects: %s\n" % e)
```

### Parameters
This endpoint does not need any parameter.

### Return type

[**SessionTemplateRecalcOutput**](SessionTemplateRecalcOutput.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **recalc_project**
> SessionTemplateRecalcOutput recalc_project(project_id)

Recalculate if sessions in the project satisfy the template.

Returns list of modified session ids.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 

try:
    # Recalculate if sessions in the project satisfy the template.
    api_response = api_instance.recalc_project(project_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->recalc_project: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 

### Return type

[**SessionTemplateRecalcOutput**](SessionTemplateRecalcOutput.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **remove_project_rule**
> InlineResponse200 remove_project_rule(project_id, rule_id)

Remove a project rule.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
rule_id = 'rule_id_example' # str | 

try:
    # Remove a project rule.
    api_response = api_instance.remove_project_rule(project_id, rule_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->remove_project_rule: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **rule_id** | **str**|  | 

### Return type

[**InlineResponse200**](InlineResponse200.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **remove_project_template**
> InlineResponse200 remove_project_template(project_id)

Remove the session template for a project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 

try:
    # Remove the session template for a project.
    api_response = api_instance.remove_project_template(project_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->remove_project_template: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 

### Return type

[**InlineResponse200**](InlineResponse200.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **rename_project_tag**
> InlineResponse2001 rename_project_tag(project_id, tag_value, body=body)

Rename a tag.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
tag_value = 'tag_value_example' # str | The tag to interact with
body = flywheel.Tag() # Tag |  (optional)

try:
    # Rename a tag.
    api_response = api_instance.rename_project_tag(project_id, tag_value, body=body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->rename_project_tag: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **tag_value** | **str**| The tag to interact with | 
 **body** | [**Tag**](Tag.md)|  | [optional] 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **replace_project_file**
> replace_project_file(project_id, file_name)

Replace a file

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
file_name = 'file_name_example' # str | 

try:
    # Replace a file
    api_instance.replace_project_file(project_id, file_name)
except ApiException as e:
    print("Exception when calling ProjectsApi->replace_project_file: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **file_name** | **str**|  | 

### Return type

void (empty response body)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **set_project_template**
> InlineResponse2001 set_project_template(project_id, body=body)

Set the session template for a project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
body = flywheel.ProjectTemplate() # ProjectTemplate |  (optional)

try:
    # Set the session template for a project.
    api_response = api_instance.set_project_template(project_id, body=body)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->set_project_template: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **body** | [**ProjectTemplate**](ProjectTemplate.md)|  | [optional] 

### Return type

[**InlineResponse2001**](InlineResponse2001.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **start_project_packfile_upload**
> PackfileStart start_project_packfile_upload(project_id)

Start a packfile upload to project

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 

try:
    # Start a packfile upload to project
    api_response = api_instance.start_project_packfile_upload(project_id)
    pprint(api_response)
except ApiException as e:
    print("Exception when calling ProjectsApi->start_project_packfile_upload: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 

### Return type

[**PackfileStart**](PackfileStart.md)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **upload_file_to_project**
> upload_file_to_project(project_id, file)

Upload a file to project.

### Example
```python
from __future__ import print_function
import time
import flywheel
from flywheel.rest import ApiException
from pprint import pprint

# Configure API key authorization: ApiKey
configuration = flywheel.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'
# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['Authorization'] = 'Bearer'

# create an instance of the API class
api_instance = flywheel.ProjectsApi(flywheel.ApiClient(configuration))
project_id = 'project_id_example' # str | 
file = '/path/to/file.txt' # file | The file to upload

try:
    # Upload a file to project.
    api_instance.upload_file_to_project(project_id, file)
except ApiException as e:
    print("Exception when calling ProjectsApi->upload_file_to_project: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **project_id** | **str**|  | 
 **file** | **file**| The file to upload | 

### Return type

void (empty response body)

### Authorization

[ApiKey](../README.md#ApiKey)

### HTTP request headers

 - **Content-Type**: multipart/form-data
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)
