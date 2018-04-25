# Copy docs to target folder
copy_sdk_docs() {
    dest_dir=$1

    # Ensure that target exists
    mkdir -p "${dest_dir}"

    # Cleanup old docs, if necessary
    rm -rf "${dest_dir}/python" "${dest_dir}/matlab"

    # Python docs
    cp -R sdk/src/python/sphinx/build "${dest_dir}/python"

    # Matlab docs
    cp -R sdk/src/matlab/build/gen/sphinx/build "${dest_dir}/matlab"
}

copy_swagger_docs() {
    dest_dir=$1

    # Ensure that target exists
    mkdir -p "${dest_dir}"

    # Cleanup old docs, if necessary
    rm -f ${dest_dir}/index.html
    rm -rf "${dest_dir}/swagger"

    cp -R swagger/build/swagger-ui "${dest_dir}/swagger"
}