package io.flywheel.rest;

public class HttpClientInit {

    static {
        // Put one-time initializations in this block

        // Ensure that we'll be able to connect to modern secure web services
        SecurityPolicy.enableUnlimitedCryptography();

        // Set default protocols to [TLSv1.2, TLSv1.1]
        HttpsSocketFactory.register();
    }

    public static void initialize() {

    }
}
