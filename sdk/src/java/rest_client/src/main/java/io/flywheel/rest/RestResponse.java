package io.flywheel.rest;

import java.io.IOException;

/**
 * Interface for querying response data
 */
public interface RestResponse {

    /**
     * Gets the http status code
     * @return The status code, or 0 if the request wasn't completed successfully
     */
    public int getStatusCode();

    /**
     * Gets the http reason phrase
     * @return The http reason phrase, or null if the request wasn't completed successfully
     */
    public String getReasonPhrase();

    /**
     * Gets the http response body as a string
     * @return The response body as a string, or empty string if there is no response.
     */
    public String getResponseBodyAsString() throws IOException;

    /**
     * Get all of the headers that match name
     * @param name The case-insensitive name of headers to retrieve
     * @return The set of headers that match name
     */
    public String[] getHeaders(String name);

    /**
     * Get the first header that matches name
     * @param name The case-insensitive name of the header to retrieve
     * @return The value of the first instance of the header name, or null if not found
     */
    public String getFirstHeader(String name);

    /**
     * Get the names of all of the headers on the response
     * @return An array of all response headers
     */
    public String[] getAllHeaderNames();
}
