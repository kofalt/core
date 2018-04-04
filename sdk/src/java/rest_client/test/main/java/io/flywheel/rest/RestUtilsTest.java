package io.flywheel.rest;

import org.junit.jupiter.api.function.Executable;

import java.util.Map;
import java.util.TreeMap;

import static org.junit.jupiter.api.Assertions.*;

class RestUtilsTest {

    @org.junit.jupiter.api.Test
    void resolvePathParameters() {
        String result = RestUtils.resolvePathParameters("/groups/{GroupId}",
                new Object[]{"GroupId", "group1"});

        assertEquals("/groups/group1", result);

        assertThrows(IllegalArgumentException.class, new Executable() {
            @Override
            public void execute() throws Throwable {
                RestUtils.resolvePathParameters("/groups/{GroupId}", null);
            }
        });

        assertThrows(IllegalArgumentException.class, new Executable() {
            @Override
            public void execute() throws Throwable {
                RestUtils.resolvePathParameters("/groups/{GroupId}", new Object[]{"GroupId"});
            }
        });

        assertThrows(IllegalArgumentException.class, new Executable() {
            @Override
            public void execute() throws Throwable {
                RestUtils.resolvePathParameters("/groups/{GroupId}", new Object[]{});
            }
        });
    }

    @org.junit.jupiter.api.Test
    void buildQueryString() {
        Map<String, String> defaults = new TreeMap<>();
        defaults.put("key1", "Value 1");

        String result = RestUtils.buildQueryString(defaults, new Object[]{"key2", null, "Key 3", false});
        assertEquals("?key1=Value%201&key2&Key%203=false", result);
    }

}