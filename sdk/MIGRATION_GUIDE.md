# SDK Migration Guide

## Migrating from SDK 0.x.y

In general, the core APIs are largely unchanged. Objects returned by APIs are now models rather than pure dictionaries or structs, 
but are still addressable in the same way. For API methods that take an object, you can pass either a dictionary (as in SDK1) or one
of the new models. See individual API doc strings for details.

* The **searchRaw** method is no longer provided.

#### Analyses

The `get_analyses` method now requires all 3 arguments. If you wish to get analyses for a single container, use the
`get_project_analyses` method instead (for example)

### Python Notes

Downloading a file directly to memory is now supported, for example:
```python
data = fw.download_file_from_project_as_data(project_id, filename)
```

### Matlab Notes

In general any fields that were **snake_case** have been converted to **camelCase**.

#### Search
The `return_type` field on search requests has been renamed to `returnType`. e.g.

```matlab
# This search call
results = fw.search(struct('return_type', 'project'));

# would become
results = fw.search(struct('returnType', 'project'));
```

#### Gears

The following gear fields have been renamed as part of the model changes:

* **git0x2Dcommit** -> **gitCommit**
* **rootfs0x2Dhash** -> **rootfsHash**
* **rootfs0x2Durl** -> **rootfsUrl**
 
