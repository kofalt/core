package io.flywheel.codegen;

import io.swagger.codegen.CodegenConfig;
import io.swagger.codegen.CodegenModel;
import io.swagger.codegen.CodegenProperty;
import io.swagger.codegen.SupportingFile;
import io.swagger.codegen.languages.PythonClientCodegen;
import io.swagger.models.ModelImpl;
import io.swagger.models.Swagger;
import io.swagger.models.properties.Property;

import java.util.HashMap;
import java.util.Map;

public class PythonGenerator extends PythonClientCodegen implements CodegenConfig {

    private static Map<String, String> propertySubstitutions;

    public PythonGenerator() {
        super();

        propertySubstitutions = new HashMap<>();
        propertySubstitutions.put("+", "plus");
        propertySubstitutions.put("-", "minus");
    }

    @Override
    public String getName() {
        return "fw-python";
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

        // Filespec helper file
        supportingFiles.add(new SupportingFile("file_spec.mustache", packageName, "file_spec.py"));

        // Flywheel wrapper file
        supportingFiles.add(new SupportingFile("flywheel.mustache", packageName, "flywheel.py"));
    }

    @Override
    public void preprocessSwagger(Swagger swagger) {
        FlywheelCodegenSupport.removeExtraOperationTags(swagger);
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

    @Override
    public void postProcessModelProperty(CodegenModel model, CodegenProperty property) {
        super.postProcessModelProperty(model, property);

        if( propertySubstitutions.containsKey(property.baseName) ) {
            property.name = property.nameInCamelCase = propertySubstitutions.get(property.baseName);
        }
    }
}
