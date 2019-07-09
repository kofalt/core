package io.flywheel.codegen;

import io.swagger.codegen.*;
import io.swagger.codegen.languages.GoClientCodegen;
import io.swagger.models.ModelImpl;
import io.swagger.models.Swagger;
import io.swagger.models.properties.Property;

import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class GoGenerator extends GoClientCodegen implements CodegenConfig {

    // private static final Pattern SIMPLE_SEMVER_RE = Pattern.compile("(?<semver>\\d+\\.\\d+\\.\\d+)"
    //         + "(-(?<releaseId>[a-z]+)\\.(?<releaseNum>\\d+))");

    // private static Map<String, String> PYTHON_RELEASE_ID_MAP;
    // static {
    //     PYTHON_RELEASE_ID_MAP = new HashMap<>();
    //     PYTHON_RELEASE_ID_MAP.put("alpha", "a");
    //     PYTHON_RELEASE_ID_MAP.put("beta", "b");
    //     PYTHON_RELEASE_ID_MAP.put("dev", "dev");
    //     PYTHON_RELEASE_ID_MAP.put("rc", "rc");
    // }

    public GoGenerator() {
        super();
    }

    @Override
    public String getName() {
        return "fw-go";
    }

    @Override
    protected void addAdditionPropertiesToCodeGenModel(CodegenModel codegenModel, ModelImpl swaggerModel) {
        Property srcProperty = swaggerModel.getAdditionalProperties();
        if( srcProperty != null ) {
            codegenModel.additionalPropertiesType = getSwaggerType(srcProperty);
            CodegenProperty prop = fromProperty("", srcProperty);
            codegenModel.vendorExtensions.put("x-python-additionalProperties", prop);
        }
    }

    @Override
    public void processOpts() {
        super.processOpts();

        final String modelFolder = modelPackage.replace('.', '/');

        additionalProperties.put("requests", "true");

        // // Filespec helper file
        // supportingFiles.add(new SupportingFile("file_spec.mustache", packageName, "file_spec.py"));

   		     // // Flywheel wrapper file
        // supportingFiles.add(new SupportingFile("flywheel.mustache", packageName, "flywheel.py"));
        // supportingFiles.add(new SupportingFile("client.mustache", packageName, "client.py"));

        // // Other API files
        // supportingFiles.add(new SupportingFile("view_builder.py", packageName, "view_builder.py"));
        // supportingFiles.add(new SupportingFile("finder.py", packageName, "finder.py"));
        // supportingFiles.add(new SupportingFile("util.py", packageName, "util.py"));
        // supportingFiles.add(new SupportingFile("mixins.py", modelFolder, "mixins.py"));
        // supportingFiles.add(new SupportingFile("gear_mixin.py", modelFolder, "gear_mixin.py"));
        // supportingFiles.add(new SupportingFile("gear_invocation.py", modelFolder, "gear_invocation.py"));
        // supportingFiles.add(new SupportingFile("gear_context.py", packageName, "gear_context.py"));
        // supportingFiles.add(new SupportingFile("drone_login.py", packageName, "drone_login.py"));

        // // PIP Files
        // supportingFiles.add(new SupportingFile("LICENSE.mustache", "", "LICENSE.txt"));
        // supportingFiles.add(new SupportingFile("setup-cfg.mustache", "", "setup.cfg"));

        // Remove docs (We use sphinx)
        additionalProperties.put(CodegenConstants.GENERATE_API_DOCS, false);
        additionalProperties.put(CodegenConstants.GENERATE_MODEL_DOCS, false);

        modelDocTemplateFiles.clear();
        apiDocTemplateFiles.clear();

        FlywheelCodegenSupport.removeSupportingFile(supportingFiles, "README.mustache");
    }

    @Override
    public void preprocessSwagger(Swagger swagger) {
        FlywheelCodegenSupport.preprocessSwagger(swagger);
    }

    @Override
    public Map<String, Object> postProcessOperations(Map<String, Object> objs) {
        objs = super.postProcessOperations(objs);
        return FlywheelCodegenSupport.postProcessOperations(objs, this);
    }

    @Override
    public Map<String, Object> postProcessModels(Map<String, Object> objs) {
        objs = super.postProcessModels(objs);
        return FlywheelCodegenSupport.postProcessModels(objs, this);
    }

    // @Override
    // public void setPackageVersion(String packageVersion) {
    //     Matcher m = SIMPLE_SEMVER_RE.matcher(packageVersion);
    //     // Translate from semver to python package verison
    //     // e.g. 2.1.1-beta.1 is 2.1.1b1
    //     if( m.matches() ) {
    //         String releaseId = m.group("releaseId");
    //         String releaseNum = m.group("releaseNum");

    //         if( releaseId != null && !releaseId.isEmpty() && releaseNum != null && !releaseNum.isEmpty() ) {
    //             // Convert to python version
    //             String pythonReleaseId = PYTHON_RELEASE_ID_MAP.get(releaseId);
    //             if( pythonReleaseId != null ) {
    //                 packageVersion = m.group("semver") + pythonReleaseId + releaseNum;
    //             }
    //         }
    //     }
    //     this.packageVersion = packageVersion;
    // }
}
