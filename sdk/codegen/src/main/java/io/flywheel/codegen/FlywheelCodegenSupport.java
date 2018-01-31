package io.flywheel.codegen;

import io.swagger.codegen.*;
import io.swagger.models.Operation;
import io.swagger.models.Path;
import io.swagger.models.Swagger;

import java.util.*;

public class FlywheelCodegenSupport {

    public static void removeExtraOperationTags(Swagger swagger) {
        Map<String,Path> paths = swagger.getPaths();
        for( String path: paths.keySet() ) {
            Path pathEntry = paths.get(path);
            for(Operation operation: pathEntry.getOperations()) {
                List<String> tags = operation.getTags();
                if( tags != null && tags.size() > 1 ) {
                    operation.setTags(Arrays.asList(tags.get(0)));
                }
            }
        }
    }

    public static Map<String, Object> postProcessModels(Map<String, Object> objs, DefaultCodegen gen) {
        ArrayList<Object> modelsArray = (ArrayList<Object>) objs.get("models");
        Map<String, Object> models = (Map<String, Object>) modelsArray.get(0);
        CodegenModel model = (CodegenModel) models.get("model");

        final Map<String, String> typeMapping = gen.typeMapping();
        if( typeMapping == null ) {
            return objs;
        }

        // If the model includes a list of "x-sdk-include-empty" properties, then we need to
        // push that to the individual properties. (If the properties reference other types then the
        // vendorExtensions don't get picked up)
        if( model.vendorExtensions != null && model.vendorExtensions.containsKey("x-sdk-include-empty") ) {
            List<String> emptyProps = (List<String>)model.vendorExtensions.get("x-sdk-include-empty");
            for( String propName: emptyProps ) {
                CodegenProperty prop = findPropertyByName(model, propName);
                if( prop != null ) {
                    if( prop.vendorExtensions == null ) {
                        prop.vendorExtensions = new HashMap<>();
                    }
                    prop.vendorExtensions.put("x-sdk-include-empty", true);
                }
            }
        }

        return objs;
    }

    public static Map<String, Object> postProcessOperations(Map<String, Object> objs, DefaultCodegen gen) {
        Map<String, Object> operations = (Map<String, Object>)objs.get("operations");
        if( operations == null ) {
            return objs;
        }

        List<CodegenOperation> ops = (List<CodegenOperation>)operations.get("operation");
        int size = ops.size();
        int idx = 0;
        while( idx < size ) {
            CodegenOperation op = ops.get(idx);
            if( op.vendorExtensions != null && op.vendorExtensions.containsKey("x-sdk-download-ticket") ) {
                CodegenOperation newOp = createDownloadTicketOp(op, gen);
                if( newOp != null ) {
                    ops.add(idx+1, newOp);
                    idx += 1;
                    size +=1;
                }
            }
            ++idx;
        }

        return objs;
    }

    private static CodegenOperation createDownloadTicketOp(CodegenOperation orig, DefaultCodegen gen) {
        String operationId = (String)orig.vendorExtensions.get("x-sdk-download-ticket");
        String getDownloadUrlId = makeDownloadUrlId(operationId);

        operationId = gen.toOperationId(operationId);
        getDownloadUrlId = gen.toOperationId(getDownloadUrlId);

        orig.vendorExtensions.remove("x-sdk-download-ticket");

        CodegenOperation newOp = shallowCloneOperation(orig);

        // Find the 200 response
        int responseIdx = 0;
        CodegenResponse response = null;
        for( ; responseIdx < orig.responses.size(); responseIdx++ ) {
            CodegenResponse resp = orig.responses.get(responseIdx);
            if( "200".equals(resp.code) ) {
                response = resp;
                break;
            }
        }

        // At this point the new op is the ticket operation
        newOp.operationId = operationId;
        newOp.operationIdLowerCase = DefaultCodegen.camelize(operationId, true);
        newOp.operationIdCamelCase = DefaultCodegen.camelize(operationId);
        newOp.operationIdSnakeCase = gen.snakeCase(operationId);

        newOp.produces = new ArrayList<>();
        newOp.produces.add(makeMediaType("application/json", false));

        newOp.vendorExtensions.put("x-sdk-download-url", getDownloadUrlId);

        // And orig is the download operation
        orig.produces = new ArrayList<>();
        orig.produces.add(makeMediaType("application/octet-stream", false));

        String destFileParam = gen.toVarName("dest-file");
        orig.vendorExtensions.put("x-sdk-download-file-param", destFileParam);

        removeQueryParam(orig, "ticket");

        // Update the response on the original
        if( response != null ) {
            CodegenResponse fileResp = shallowCloneResponse(response);
            orig.responses.set(responseIdx, fileResp);

            fileResp.isFile = true;
            fileResp.simpleType = false;
            fileResp.primitiveType = false;

            fileResp.dataType = null;
            fileResp.baseType = null;
            fileResp.containerType = null;

            fileResp.vendorExtensions.put("x-sdk-download-file-param", destFileParam);
        }

        return newOp;
    }

    private static String makeDownloadUrlId(String operationId) {
        return operationId.replace("_ticket", "_url");
    }


    // ugh
    private static CodegenOperation shallowCloneOperation(CodegenOperation orig) {
        CodegenOperation result = new CodegenOperation();

        result.responseHeaders.addAll(orig.responseHeaders);

        result.hasAuthMethods = orig.hasAuthMethods;
        result.hasConsumes = orig.hasConsumes;
        result.hasProduces = orig.hasProduces;
        result.hasParams = orig.hasParams;
        result.hasOptionalParams = orig.hasOptionalParams;
        result.hasRequiredParams = orig.hasRequiredParams;
        result.returnTypeIsPrimitive = orig.returnTypeIsPrimitive;
        result.returnSimpleType = orig.returnSimpleType;
        result.subresourceOperation = orig.subresourceOperation;
        result.isMapContainer = orig.isMapContainer;
        result.isListContainer = orig.isListContainer;
        result.isMultipart = orig.isMultipart;
        result.hasMore = orig.hasMore;
        result.isResponseBinary = orig.isResponseBinary;
        result.isResponseFile = orig.isResponseFile;
        result.hasReference = orig.hasReference;
        result.isRestfulIndex = orig.isRestfulIndex;
        result.isRestfulShow = orig.isRestfulShow;
        result.isRestfulCreate = orig.isRestfulCreate;
        result.isRestfulUpdate = orig.isRestfulUpdate;
        result.isRestfulDestroy = orig.isRestfulDestroy;
        result.isRestful = orig.isRestful;
        result.isDeprecated = orig.isDeprecated;

        result.path = orig.path;
        result.operationId = orig.operationId;
        result.returnType = orig.returnType;
        result.httpMethod = orig.httpMethod;
        result.returnBaseType = orig.returnBaseType;
        result.returnContainer = orig.returnContainer;
        result.summary = orig.summary;
        result.unescapedNotes = orig.unescapedNotes;
        result.notes = orig.notes;
        result.baseName = orig.baseName;
        result.defaultResponse = orig.defaultResponse;
        result.discriminator = orig.discriminator;

        if( orig.consumes != null ) {
            result.consumes = new ArrayList<>(orig.consumes);
        }
        if( orig.produces != null ) {
            result.produces = new ArrayList<>(orig.produces);
        }
        if( orig.prioritizedContentTypes != null ) {
            result.prioritizedContentTypes = new ArrayList<>(orig.prioritizedContentTypes);
        }

        result.bodyParam = orig.bodyParam;

        result.allParams.addAll(orig.allParams);
        result.bodyParams.addAll(orig.bodyParams);

        result.pathParams.addAll(orig.pathParams);
        result.queryParams.addAll(orig.queryParams);
        result.headerParams.addAll(orig.headerParams);
        result.formParams.addAll(orig.formParams);
        result.requiredParams.addAll(orig.requiredParams);

        if (orig.authMethods != null) {
            result.authMethods = new ArrayList<>(orig.authMethods);
        }

        if (orig.tags != null) {
            result.tags = new ArrayList<>(orig.tags);
        }

        result.responses.addAll(orig.responses);
        result.imports.addAll(orig.imports);

        if (orig.examples != null) {
            result.examples = new ArrayList<>(orig.examples);
        }

        if (orig.requestBodyExamples != null) {
            result.requestBodyExamples = new ArrayList<>(orig.requestBodyExamples);
        }

        result.externalDocs = orig.externalDocs;

        if (orig.vendorExtensions != null) {
            result.vendorExtensions = new HashMap<>(orig.vendorExtensions);
        }

        result.operationIdLowerCase = orig.operationIdLowerCase;
        result.operationIdCamelCase = orig.operationIdCamelCase;
        result.operationIdSnakeCase = orig.operationIdSnakeCase;

        return result;
    }

    private static CodegenResponse shallowCloneResponse(CodegenResponse orig) {
        CodegenResponse result = new CodegenResponse();

        result.headers.addAll(orig.headers);

        result.code = orig.code;
        result.message = orig.message;

        result.hasMore = orig.hasMore;
        if( orig.examples != null ) {
            result.examples = new ArrayList<>(orig.examples);
        }

        result.dataType = orig.dataType;
        result.baseType = orig.baseType;
        result.containerType = orig.containerType;

        result.hasHeaders = orig.hasHeaders;
        result.isString = orig.isString;
        result.isNumeric = orig.isNumeric;
        result.isInteger = orig.isInteger;
        result.isLong = orig.isLong;
        result.isNumber = orig.isNumber;
        result.isFloat = orig.isFloat;
        result.isDouble = orig.isDouble;
        result.isByteArray = orig.isByteArray;
        result.isBoolean = orig.isBoolean;
        result.isDate = orig.isDate;
        result.isDateTime = orig.isDateTime;
        result.isUuid = orig.isUuid;

        result.isDefault = orig.isDefault;
        result.simpleType = orig.simpleType;
        result.primitiveType = orig.primitiveType;
        result.isMapContainer = orig.isMapContainer;
        result.isListContainer = orig.isListContainer;
        result.isBinary = orig.isBinary;
        result.isFile = orig.isFile;

        result.schema = orig.schema;
        result.jsonSchema = orig.jsonSchema;

        if( orig.vendorExtensions != null ) {
            result.vendorExtensions = new HashMap<>(orig.vendorExtensions);
        }

        return result;
    }

    private static Map<String, String> makeMediaType(String mediaType, boolean hasMore) {
        Map<String, String> result = new HashMap<>();

        result.put("mediaType", mediaType);
        if( hasMore ) {
            result.put("hasMore", "true");
        } else {
            result.put("hasMore", null);
        }

        return result;
    }

    private static void removeQueryParam(CodegenOperation op, String name) {
        removeQueryParamFromList(op.allParams, name);
        removeQueryParamFromList(op.queryParams, name);
        removeQueryParamFromList(op.requiredParams, name);
    }

    private static void removeQueryParamFromList(List<CodegenParameter> params, String name) {
        Iterator<CodegenParameter> itr = params.iterator();
        while( itr.hasNext() ) {
            CodegenParameter param = itr.next();
            if( param.isQueryParam && name.equals(param.baseName) ) {
                itr.remove();
                break;
            }
        }
    }

    private static CodegenProperty findPropertyByName(CodegenModel model, String property) {
        for( CodegenProperty prop: model.allVars ) {
            if( property.equals(prop.baseName) ) {
                return prop;
            }
        }
        return null;
    }
}
