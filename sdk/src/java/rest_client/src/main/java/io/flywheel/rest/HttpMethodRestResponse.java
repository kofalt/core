package io.flywheel.rest;

import org.apache.commons.httpclient.Header;
import org.apache.commons.httpclient.HttpMethod;

import java.io.IOException;
import java.util.ArrayList;

/**
 * HttpClient 3.1 implementation of RestResponse
 * @class HttpMethodRestResponse
 */
public class HttpMethodRestResponse implements RestResponse {

    private static final String[] EMPTY_STRING_ARRAY = {};

    private final HttpMethod method;

    /**
     * Construct a RestResponse from HttpMethod
     * @param method The http method, must not be null.
     */
    public HttpMethodRestResponse(final HttpMethod method) {
        this.method = method;

        if( this.method == null ) {
            throw new IllegalArgumentException("HttpMethod cannot be null!");
        }
    }

    @Override
    public int getStatusCode() {
        return method.getStatusCode();
    }

    @Override
    public String getReasonPhrase() {
        return method.getStatusText();
    }

    @Override
    public String getResponseBodyAsString() throws IOException {
        return method.getResponseBodyAsString();
    }

    @Override
    public String[] getHeaders(String name) {
        Header[] headers = method.getResponseHeaders(name);

        if( headers == null ) {
            return EMPTY_STRING_ARRAY;
        }


        String[] result = new String[headers.length];
        for( int i = 0; i < headers.length; i++ ) {
            result[i] = headers[i].getValue();
        }
        return result;
    }

    @Override
    public String getFirstHeader(String name) {
        Header result = method.getResponseHeader(name);
        if( result == null ) {
            return null;
        }
        return result.getValue();
    }

    @Override
    public String[] getAllHeaderNames() {
        Header[] headers = method.getResponseHeaders();
        if( headers == null ) {
            return EMPTY_STRING_ARRAY;
        }
        String[] result = new String[headers.length];
        for( int i = 0; i < headers.length; i++ ) {
            result[i] = headers[i].getName();
        }
        return result;
    }
}
