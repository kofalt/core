package io.flywheel.rest;

import javax.crypto.Cipher;
import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.security.NoSuchAlgorithmException;
import java.security.Permission;
import java.security.PermissionCollection;
import java.util.Map;
import java.util.logging.Logger;

public class SecurityPolicy {

    private final static Logger LOGGER = Logger.getLogger("io.flywheel");

    private static boolean isRestrictedCryptography() throws NoSuchAlgorithmException {
        return Cipher.getMaxAllowedKeyLength("AES/ECB/NoPadding") < 256;
    }

    /**
     * Enables unlimited cryptography (i.e. AES-256 and SHA-2 algorithms)
     * NOTE: Newer releases of the JVM ship with this enabled, and Matlab makes use of
     * these algorithms in other avenues. If we don't enable this, we can't talk to modern
     * secure web servers.
     */
    public static void enableUnlimitedCryptography() {
        try {
            // Skip modifying final static members if we don't need to
            if( !isRestrictedCryptography() ) {
                return;
            }

            final Class<?> jceSecurity = Class.forName("javax.crypto.JceSecurity");
            final Class<?> cryptoPermissions = Class.forName("javax.crypto.CryptoPermissions");
            final Class<?> cryptoAllPermission = Class.forName("javax.crypto.CryptoAllPermission");

            Field isRestrictedField = jceSecurity.getDeclaredField("isRestricted");
            setFinalStatic(isRestrictedField, false);

            final Field defaultPolicyField = jceSecurity.getDeclaredField("defaultPolicy");
            defaultPolicyField.setAccessible(true);
            final PermissionCollection defaultPolicy = (PermissionCollection) defaultPolicyField.get(null);

            final Field perms = cryptoPermissions.getDeclaredField("perms");
            perms.setAccessible(true);
            ((Map)perms.get(defaultPolicy)).clear();

            final Field instance = cryptoAllPermission.getDeclaredField("INSTANCE");
            instance.setAccessible(true);
            defaultPolicy.add((Permission) instance.get(null));

        } catch( Exception e ) {
            LOGGER.severe("Could not enable unlimited cryptography: " + e.getMessage());
            e.printStackTrace();
            System.err.println("Unable to enable unlimited cryptography: " + e.getMessage());
        }
    }

    private static void setFinalStatic(Field field, Object newValue) throws Exception {
        field.setAccessible(true);

        Field modifiersField = Field.class.getDeclaredField("modifiers");
        modifiersField.setAccessible(true);
        modifiersField.setInt(field, field.getModifiers() & ~Modifier.FINAL);

        field.set(null, newValue);
    }
}
