package io.flywheel.codegen;

import com.sun.org.apache.xpath.internal.operations.Bool;
import io.swagger.codegen.*;
import io.swagger.models.properties.*;
import org.apache.commons.lang3.StringUtils;

import java.util.*;
import java.io.File;

public class MatlabGenerator extends DefaultCodegen implements CodegenConfig {

  // source folder where to write the files
  protected String sourceFolder = "src";
  protected String apiVersion = "1.0.0";

  protected String packageName;

  /**
   * Configures the type of generator.
   * 
   * @return  the CodegenType for this generator
   * @see     io.swagger.codegen.CodegenType
   */
  public CodegenType getTag() {
    return CodegenType.CLIENT;
  }

  /**
   * Configures a friendly name for the generator.  This will be used by the generator
   * to select the library with the -l flag.
   * 
   * @return the friendly name for the generator
   */
  public String getName() {
    return "matlab";
  }

  /**
   * Returns human-friendly help for the generator.  Provide the consumer with help
   * tips, parameters here
   * 
   * @return A string value for the help message
   */
  public String getHelp() {
    return "Generates a matlab client library.";
  }

  public MatlabGenerator() {
    super();

    importMapping.clear();

    // set the output folder here
    outputFolder = "generated-code/matlab";

    /**
     * Models.  You can write model files using the modelTemplateFiles map.
     * if you want to create one template for file, you can do so here.
     * for multiple files for model, just put another entry in the `modelTemplateFiles` with
     * a different extension
     */
    modelTemplateFiles.put(
      "model.mustache", // the template to use
      ".m");       // the extension for each file to write

    /**
     * Api classes.  You can write classes for each Api file with the apiTemplateFiles map.
     * as with models, add multiple entries with different extensions for multiple files per
     * class
     */
    apiTemplateFiles.put(
      "api.mustache",   // the template to use
      ".m");       // the extension for each file to write

    /**
     * Template Location.  This is the location which templates will be read from.  The generator
     * will use the resource stream to attempt to read the templates.
     */
    templateDir = "matlab";

    /**
     * Api Package.  Optional, if needed, this can be used in templates
     */
    apiPackage = "api";

    /**
     * Model Package.  Optional, if needed, this can be used in templates
     */
    modelPackage = "model";

    /**
     * Reserved words.  Override this with reserved words specific to your language
     */
    reservedWords = new HashSet<String> (
      Arrays.asList(
        "break",
        "case",
        "catch",
        "classdef",
        "continue",
        "else",
        "elseif",
        "end",
        "for",
        "function",
        "global",
        "if",
        "otherwise",
        "parfor",
        "persistent",
        "return",
        "spmd",
        "switch",
        "try",
        "while")
    );

    /**
     * Additional Properties.  These values can be passed to the templates and
     * are available in models, apis, and supporting files
     */
    additionalProperties.put("apiVersion", apiVersion);

    /**
     * Supporting Files.  You can write single files for the generator with the
     * entire object tree available.  If the input file has a suffix of `.mustache
     * it will be processed by the template engine.  Otherwise, it will be copied
     */
    /*
    supportingFiles.add(new SupportingFile("myFile.mustache",   // the input template or file
      "",                                                       // the destination folder, relative `outputFolder`
      "myFile.sample")                                          // the output file
    );
    */

    /**
     * Language Specific Primitives.  These types will not trigger imports by
     * the client generator
     */
    languageSpecificPrimitives = new HashSet<String>(
      Arrays.asList(
        "Type1",      // replace these with your types
        "Type2")
    );
  }

  @Override
  public void processOpts() {
    super.processOpts();

    if (additionalProperties.containsKey(CodegenConstants.PACKAGE_NAME)) {
      packageName = (String) additionalProperties.get(CodegenConstants.PACKAGE_NAME);
    } else {
      packageName = "swagger_client";
    }

    modelPackage = packageName + "." + modelPackage;
    apiPackage = packageName + "." + apiPackage;
  }

  /**
   * Escapes a reserved word as defined in the `reservedWords` array. Handle escaping
   * those terms here.  This logic is only called if a variable matches the reserved words
   * 
   * @return the escaped term
   */
  @Override
  public String escapeReservedWord(String name) {
    return "x_" + name;  // add an underscore to the name
  }

  /**
   * Location to write model files.  You can use the modelPackage() as defined when the class is
   * instantiated
   */
  public String modelFileFolder() {
    return outputFolder + "/" + sourceFolder + "/" + modelPackage().replace('.', File.separatorChar);
  }

  /**
   * Location to write api files.  You can use the apiPackage() as defined when the class is
   * instantiated
   */
  @Override
  public String apiFileFolder() {
    return outputFolder + "/" + sourceFolder + "/" + apiPackage().replace('.', File.separatorChar);
  }

  /**
   * Optional - type declaration.  This is a String which is used by the templates to instantiate your
   * types.  There is typically special handling for different property types
   *
   * @return a string value used as the `dataType` field for model templates, `returnType` for api templates
   */
  @Override
  public String getTypeDeclaration(Property p) {
    if(p instanceof ArrayProperty) {
      ArrayProperty ap = (ArrayProperty) p;
      Property inner = ap.getItems();
      return getSwaggerType(p) + "[" + getTypeDeclaration(inner) + "]";
    }
    else if (p instanceof MapProperty) {
      MapProperty mp = (MapProperty) p;
      Property inner = mp.getAdditionalProperties();
      return getSwaggerType(p) + "[String, " + getTypeDeclaration(inner) + "]";
    }
    return super.getTypeDeclaration(p);
  }

  /**
   * Optional - swagger type conversion.  This is used to map swagger types in a `Property` into 
   * either language specific types via `typeMapping` or into complex models if there is not a mapping.
   *
   * @return a string value of the type or complex model for this property
   * @see io.swagger.models.properties.Property
   */
  @Override
  public String getSwaggerType(Property p) {
    String swaggerType = super.getSwaggerType(p);
    String type = null;
    if(typeMapping.containsKey(swaggerType)) {
      type = typeMapping.get(swaggerType);
      if(languageSpecificPrimitives.contains(type))
        return toModelName(type);
    }
    else
      type = swaggerType;
    return toModelName(type);
  }

  @Override
  public String toModelName(String name) {
    name = sanitizeName(name);

    // Must begin with a letter, strip any other characters from the front
    name = stripLeader(name);

    // Replace every other non-word character with an underscore (compressing multiples)
    name = name.replaceAll("[^\\w]+", "_");

    // If it begins with a digit, add "Model" prefix
    if( name.matches("^\\d.*") ) {
      LOGGER.warn(name + " (model name starts with number) cannot be used as model name. Renamed to " + camelize("model_" + name));
      name = "model_" + name; // e.g. 200Response => Model200Response (after camelize)
    }

    return camelize(name);
  }

  @Override
  public String toModelFilename(String name) {
    return toModelName(name);
  }

  @Override
  public String toVarName(String name) {
    name = sanitizeName(name);
    name = underscore(name);

    // Must begin with a letter, strip any other characters from the front
    name = stripLeader(name);

    // Replace every other non-word character with an underscore (compressing multiples)
    name = name.replaceAll("[^\\w]+", "_");

    // If we end up with a reserved word or
    if( isReservedWord(name) || name.matches("^\\d.*") ) {
      name = escapeReservedWord(name);
    }

    return camelize(name, true);
  }

  @Override
  public String toApiName(String name) {
    if (name.length() == 0) {
      return "DefaultApi";
    }
    return camelize(name) + "Api";
  }

  @Override
  public String toOperationId(String operationId) {
    if(StringUtils.isEmpty(operationId)) {
      throw new RuntimeException("Empty method name (operationId) is not allowed");
    }
    if(isReservedWord(operationId)) {
      LOGGER.warn(operationId + " (reserved word) cannot be used as method name.");
      operationId = "call_" + operationId;
    }
    return camelize(sanitizeName(operationId), true);
  }

  @Override
  public String toDefaultValue(Property p) {
    if( p instanceof StringProperty ) {
      StringProperty dp = (StringProperty)p;
      if( dp.getDefault() != null ) {
        return "'" + dp.getDefault().replace("'", "''")
                .replace("\n", "\\n")
                .replace("\r", "\\r") + "'";
      }
    } else if( p instanceof BooleanProperty ) {
      BooleanProperty dp = (BooleanProperty)p;
      if( dp.getDefault() != null ) {
        if( dp.getDefault().toString().equalsIgnoreCase("false") ) {
          return "false";
        }
        return "true";
      }
    } else if( p instanceof DoubleProperty ) {
      DoubleProperty dp = (DoubleProperty)p;
      if( dp.getDefault() != null ) {
        return dp.getDefault().toString();
      }
    } else if( p instanceof FloatProperty ) {
      FloatProperty dp = (FloatProperty)p;
      if( dp.getDefault() != null ) {
        return dp.getDefault().toString();
      }
    } else if( p instanceof IntegerProperty ) {
      IntegerProperty dp = (IntegerProperty)p;
      if( dp.getDefault() != null ) {
        return dp.getDefault().toString();
      }
    } else if( p instanceof LongProperty ) {
      LongProperty dp = (LongProperty)p;
      if( dp.getDefault() != null ) {
        return dp.getDefault().toString();
      }
    }
    return null;
  }

  @Override
  public void postProcessModelProperty(CodegenModel model, CodegenProperty property) {
    super.postProcessModelProperty(model, property);

    // Add matlab name
    String matlabName = makeValidMatlabNameHex(property.baseName);
    property.vendorExtensions.put("x-matlab-baseName", matlabName);
  }

  @Override
  public String escapeUnsafeCharacters(String input) {
    // remove multi-line comments
    return input.replace("%{", "{")
            .replace("%}", "}");
  }

  @Override
  public String escapeQuotationMark(String input) {
    return input.replace("'", "''");
  }

  private static String stripLeader(String name) {
    int idx = 0;
    while( idx < name.length() && !isAsciiLetterOrNumber(name.charAt(idx)) ) {
      ++idx;
    }

    if( idx > 0 ) {
      return name.substring(idx);
    }

    return name;
  }

  private static String makeValidMatlabName(String input, final String prefix) {
    // The best I can tell is that matlab splits the input string on whitespace
    // Uppercases any parts beyond the first
    // Replaces any non-word character with underscore
    // Finally, if the name begins with a non-alphabet character, prefix it
    input = stripMatlabName(input);

    input = input.replaceAll("[^\\w]", "_");

    if( input.isEmpty() || !isAsciiLetter(input.charAt(0)) ) {
      input = prefix + input;
    }

    return input;
  }

  private static String makeValidMatlabName(String input) {
    return makeValidMatlabName(input, "x");
  }

  private static String makeValidMatlabNameHex(String input) {
    input = stripMatlabName(input);

    // Replace
    String result = "";
    for( int i = 0; i < input.length(); i++ ) {
      char c = input.charAt(i);
      if( i == 0 && c == '_' ) {
        result = result + makeHexReplacement(c);
      } else if( isValidMatlabCharacter(c) ) {
        result = result + c;
      } else {
        result = result + makeHexReplacement(c);
      }
    }

    if( result.isEmpty() || !isAsciiLetter(result.charAt(0)) ) {
      result = "x" + result;
    }

    return result;
  }

  private static String stripMatlabName(String input) {
    String[] parts =  input.split("\\s+");
    input = "";
    for( String part : parts ) {
      if( part.isEmpty() ) {
        continue;
      }
      if( input.isEmpty() ) {
        input = part;
      } else {
        input = input + part.substring(0, 1).toUpperCase() + part.substring(1);
      }
    }
    return input;
  }

  private static boolean isAsciiLetter(char c) {
    return (c >= 65 && c <= 90) ||
            (c >= 97 && c <= 122 );
  }

  private static boolean isAsciiNumber(char c) {
    return (c >= 48 && c <= 57);
  }

  private static boolean isAsciiLetterOrNumber(char c) {
    return isAsciiLetter(c) || isAsciiNumber(c);
  }

  private static String makeHexReplacement(char c) {
    String repl = Integer.toHexString((int)c);
    while( repl.length() < 2 ) {
      repl = "0" + repl;
    }
    return "0x" + repl.toUpperCase();
  }

  private static boolean isValidMatlabCharacter(char c) {
    return c == '_' || isAsciiLetter(c) || isAsciiNumber(c);
  }

}