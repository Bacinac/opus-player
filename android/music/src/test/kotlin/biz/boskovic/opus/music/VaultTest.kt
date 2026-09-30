package biz.boskovic.opus.music

import java.security.KeyStoreException
import java.security.ProviderException
import java.security.UnrecoverableKeyException
import javax.crypto.AEADBadTagException
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class VaultTest {
    @Test
    fun `a ciphertext the key does not open is lost for good`() {
        assertTrue(Vault.broken(AEADBadTagException("Invalid tag"), keystoreSaysGone = false))
        assertTrue(Vault.broken(ProviderException("Keystore operation failed", AEADBadTagException()), keystoreSaysGone = false))
    }

    @Test
    fun `the keystore saying the key is gone or corrupt is lost for good`() {
        assertTrue(Vault.broken(ProviderException("Keystore operation failed"), keystoreSaysGone = true))
        assertTrue(Vault.broken(UnrecoverableKeyException("Failed to obtain information about key"), keystoreSaysGone = true))
    }

    @Test
    fun `a keystore that is busy, restarting or unreadable may answer next time`() {
        assertFalse(Vault.broken(ProviderException("Keystore operation failed"), keystoreSaysGone = false))
        assertFalse(Vault.broken(UnrecoverableKeyException("Failed to obtain information about key"), keystoreSaysGone = false))
        assertFalse(Vault.broken(KeyStoreException("System error"), keystoreSaysGone = false))
    }
}
