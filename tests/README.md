## Testing
Build flywheel/core and run automated tests in a docker container:
```
./tests/bin/docker-tests.sh
```

* All tests (unit, integration and linting) are executed by default
* To enter a test shell, use `--shell` (`-s`)
* To skip building the image, use `--no-build` (`-B`)
* To skip linting, use `--skip-lint` (`-L`)
* Conversely, run linting only with `--lint-only` (`-l`)
* Any additional arguments are passed to `py.test`:
    * To run only a subset of test, use the [keyword expression filter](https://docs.pytest.org/en/latest/usage.html#specifying-tests-selecting-tests) `-k`
    * To see `print` output during tests, increase verbosity with `-vvv`
    * To get a debugger session on failures, use [`--pdb`](https://docs.pytest.org/en/latest/usage.html#dropping-to-pdb-python-debugger-on-failures)

See [py.test usage](https://docs.pytest.org/en/latest/usage.html) for more.

### Example
The most common use case is adding a new (still failing) test, and wanting to
* (re-)run it as fast as possible
   * skip building with `-B`
   * skip linting with `-L`
   * skip all other tests but 'foo' with `-k foo`
* see output from quick and dirty `print` statements in the test (`-vvv`)
* get into an interactive pdb session to inspect what went wrong (`--pdb`)

```
./tests/bin/docker-tests.sh -B -L -k foo -vvv --pdb
```
