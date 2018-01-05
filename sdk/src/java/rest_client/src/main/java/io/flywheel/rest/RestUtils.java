package io.flywheel.rest;

import org.apache.commons.httpclient.HttpMethod;
import org.apache.commons.httpclient.methods.*;

import java.lang.reflect.Constructor;
import java.util.Map;
import java.util.TreeMap;

public class RestUtils {

    private static Map<String, Constructor<? extends HttpMethod>> METHOD_MAP;

    static {
        METHOD_MAP = new TreeMap<>();
        try {
            METHOD_MAP.put("get", GetMethod.class.getConstructor(String.class));
            METHOD_MAP.put("put", PutMethod.class.getConstructor(String.class));
            METHOD_MAP.put("post", PostMethod.class.getConstructor(String.class));
            METHOD_MAP.put("delete", DeleteMethod.class.getConstructor(String.class));
            METHOD_MAP.put("options", OptionsMethod.class.getConstructor(String.class));
        } catch (NoSuchMethodException e) {
            // Should never happen
        }
    }

    public static HttpMethod createMethod(String method, String url) {
        Constructor<? extends HttpMethod> ctor = METHOD_MAP.get(method.toLowerCase());
        if( ctor == null ) {
            throw new IllegalArgumentException("Unknown method: " + method);
        }

        try {
            return ctor.newInstance(url);
        } catch( Exception e ) {
            // None of these should happen, but convert them to a runtime error
            throw new RuntimeException("Unable to construct method", e);
        }
    }

}
