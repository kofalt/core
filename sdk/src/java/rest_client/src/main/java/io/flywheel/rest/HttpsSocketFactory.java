package io.flywheel.rest;

import org.apache.commons.httpclient.ConnectTimeoutException;
import org.apache.commons.httpclient.params.HttpConnectionParams;
import org.apache.commons.httpclient.protocol.Protocol;
import org.apache.commons.httpclient.protocol.ProtocolSocketFactory;

import javax.net.ssl.*;
import java.io.IOException;
import java.io.InputStream;
import java.net.*;
import java.security.KeyStore;
import java.security.KeyStoreException;
import java.security.NoSuchAlgorithmException;
import java.security.cert.CertificateException;
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

    private SSLContext sslContext = null;

    private SSLContext getSSLContext() {
        if (this.sslContext == null ) {
            this.sslContext = createSSLContext();
        }
        return this.sslContext;
    }

    private KeyStore createKeystore() {
        InputStream in = null;
        try {
            in = getClass().getResourceAsStream("/io/flywheel/rest/cacerts");
            KeyStore ks = KeyStore.getInstance("JKS");
            ks.load(in, null);
            return ks;
        } catch (Exception e) {
            e.printStackTrace();
            return null;
        } finally {
            try {
                in.close();
            } catch( Exception e ) {}
        }
    }

    private SSLContext createSSLContext() {
        try {
            KeyStore ks = createKeystore();
            if( ks == null ) {
                return null;
            }

            TrustManagerFactory tmf = TrustManagerFactory.getInstance("SunX509");
            tmf.init(ks);

            SSLContext context = SSLContext.getInstance("TLS");
            context.init(null, tmf.getTrustManagers(), null);

            return context;
        } catch(Exception e) {
            e.printStackTrace();
            return null;
        }
    }

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
        Socket result;
        SSLContext context = this.getSSLContext();
        if( context != null ) {
            result = context.getSocketFactory().createSocket(s, i, inetAddress, i1);
        } else {
            result = baseFactory.createSocket(s, i, inetAddress, i1);
        }
        return setProtocols(result);
    }

    @Override
    public Socket createSocket(String s, int i, InetAddress inetAddress, int i1, HttpConnectionParams httpConnectionParams) throws IOException, UnknownHostException, ConnectTimeoutException {
        if( httpConnectionParams == null ) {
            throw new IllegalArgumentException("Parameters may not be null");
        }
        int timeout = httpConnectionParams.getConnectionTimeout();
        Socket result;
        SSLContext context = this.getSSLContext();
        if( context != null ) {
            if( timeout == 0 ) {
                result = context.getSocketFactory().createSocket(s, i, inetAddress, i1);
                setProtocols(result);
            } else {
                result = context.getSocketFactory().createSocket();
                SocketAddress localaddr = new InetSocketAddress(inetAddress, i1);
                SocketAddress remoteaddr = new InetSocketAddress(s, i);
                setProtocols(result);
                result.bind(localaddr);
                result.connect(remoteaddr, timeout);
            }
        } else {
            result = baseFactory.createSocket(s, i, inetAddress, i1, httpConnectionParams);
            setProtocols(result);
        }
        return result;
    }

    @Override
    public Socket createSocket(String s, int i) throws IOException, UnknownHostException {
        Socket result;
        SSLContext context = this.getSSLContext();
        if( context != null ) {
            result = context.getSocketFactory().createSocket(s, i);
        } else {
            result = baseFactory.createSocket(s, i);
        }
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
