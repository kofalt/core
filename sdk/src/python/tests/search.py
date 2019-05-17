import flywheel
import os

project_query = "Test"
file_query = "alice.txt"

if __name__ == "__main__":
    api_key = os.environ["SdkTestKey"]
    fw = flywheel.Flywheel(api_key)

    results = fw.search({"return_type": "project", "search_string": project_query})
    assert len(results) >= 1

    for result in results:
        print("Project: {}".format(result.project.label))
        for f in result.project.files:
            print("  file: {}".format(f["name"]))

        for s in result.project.sessions:
            print("  session: {}".format(s.label))

    results = fw.search({"return_type": "file", "search_string": file_query})
    for result in results:
        print("File result: {}".format(result.file.name))
        print("  url: {}".format(result.file.url))
