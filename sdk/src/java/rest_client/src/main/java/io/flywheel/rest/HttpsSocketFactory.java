package io.flywheel.rest;

import org.apache.commons.httpclient.ConnectTimeoutException;
import org.apache.commons.httpclient.params.HttpConnectionParams;
import org.apache.commons.httpclient.protocol.Protocol;
import org.apache.commons.httpclient.protocol.ProtocolSocketFactory;

import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;
import java.io.IOException;
import java.net.InetAddress;
import java.net.Socket;
import java.net.UnknownHostException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class HttpsSocketFactory implements ProtocolSocketFactory {

    private final ProtocolSocketFactory baseFactory;
    private final String[] enabledProtocols;

    private final String[] enabledCipherSuites;

    private static final String[] DEFAULT_PROTOCOLS = {"TLSv1.2", "TLSv1.1"};
    private static final String[] DESIRED_CIPHER_SUITES = {
            "TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA384",
            "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384",
            "TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256",
            "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
            "TLS_DHE_DSS_WITH_AES_256_GCM_SHA384",
            "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
            "TLS_DHE_DSS_WITH_AES_128_GCM_SHA256",
            "TLS_DHE_DSS_WITH_AES_256_CBC_SHA256",
            "TLS_DHE_RSA_WITH_AES_256_CBC_SHA256",
            "TLS_RSA_WITH_AES_256_CBC_SHA256",
            "TLS_RSA_WITH_AES_128_CBC_SHA256"
    };

    private HttpsSocketFactory(ProtocolSocketFactory baseFactory, String[] enabledProtocols) {
        if( baseFactory == null ) {
            throw new IllegalArgumentException("baseFactory is required!");
        }

        this.baseFactory = baseFactory;
        this.enabledProtocols = enabledProtocols;
        this.enabledCipherSuites = determineEnabledCipherSuites();
    }

    private HttpsSocketFactory(ProtocolSocketFactory baseFactory) {
        this(baseFactory, DEFAULT_PROTOCOLS);
    }

    @Override
    public Socket createSocket(String s, int i, InetAddress inetAddress, int i1) throws IOException, UnknownHostException {
        Socket result = baseFactory.createSocket(s, i, inetAddress, i1);
        return setProtocols(result);
    }

    @Override
    public Socket createSocket(String s, int i, InetAddress inetAddress, int i1, HttpConnectionParams httpConnectionParams) throws IOException, UnknownHostException, ConnectTimeoutException {
        Socket result = baseFactory.createSocket(s, i, inetAddress, i1, httpConnectionParams);
        return setProtocols(result);
    }

    @Override
    public Socket createSocket(String s, int i) throws IOException, UnknownHostException {
        Socket result = baseFactory.createSocket(s, i);
        return setProtocols(result);
    }

    private Socket setProtocols(Socket socket) {
        if( socket instanceof SSLSocket ) {
            SSLSocket sslSocket = (SSLSocket)socket;
            sslSocket.setEnabledProtocols(enabledProtocols);
            if( enabledCipherSuites != null && enabledCipherSuites.length > 0 ) {
                sslSocket.setEnabledCipherSuites(enabledCipherSuites);
            }
        }
        return socket;
    }

    public static void register() {
        Protocol baseProtocol = Protocol.getProtocol("https");
        int defaultPort = baseProtocol.getDefaultPort();

        HttpsSocketFactory customFactory = new HttpsSocketFactory(baseProtocol.getSocketFactory());

        Protocol customProtocol = new Protocol("https", customFactory, defaultPort);
        Protocol.registerProtocol("https", customProtocol);
    }

    public static String[] determineEnabledCipherSuites() {
        ArrayList<String> result = new ArrayList<>();
        try {
            SSLSocket sock = (SSLSocket)SSLSocketFactory.getDefault().createSocket();

            // Add desired suites first
            List<String> supportedSuites = Arrays.asList(sock.getSupportedCipherSuites());
            for( String suite : DESIRED_CIPHER_SUITES ) {
                if( supportedSuites.contains(suite) ) {
                    result.add(suite);
                }
            }

            // Add remaining suites
            String[] enabledSuites = sock.getEnabledCipherSuites();
            for( String suite : enabledSuites ) {
                result.add(suite);
            }
        } catch( Exception e ) {
            e.printStackTrace();
        }

        return result.toArray(new String[result.size()]);
    }
}
