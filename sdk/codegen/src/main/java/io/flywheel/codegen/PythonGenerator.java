package io.flywheel.codegen;

import io.swagger.codegen.CodegenModel;
import io.swagger.codegen.CodegenProperty;
import io.swagger.codegen.languages.PythonClientCodegen;
import io.swagger.models.ModelImpl;
import io.swagger.models.properties.Property;

public class PythonGenerator extends PythonClientCodegen {

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

}
