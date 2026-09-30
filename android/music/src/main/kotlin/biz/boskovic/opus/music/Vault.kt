package biz.boskovic.opus.music

import android.os.Build
import android.security.KeyStoreException as KeystoreFailure
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.annotation.RequiresApi
import java.io.IOException
import java.security.GeneralSecurityException
import java.security.KeyStore
import java.security.ProviderException
import java.security.UnrecoverableKeyException
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

internal interface Sealer {
    /** @throws SealUnavailable when nothing could be sealed this time. */
    fun seal(plain: String): String

    /** @throws SealBroken when [sealed] can never be opened again.
     *  @throws SealUnavailable when it could not be opened this time. */
    fun open(sealed: String): String
}

internal class SealBroken(message: String, cause: Throwable? = null) : GeneralSecurityException(message, cause)

internal class SealUnavailable(cause: Throwable) : GeneralSecurityException("the keystore did not answer: ${cause.message}", cause)

/** AES-GCM under a key that never leaves the Android Keystore. */
internal object Vault : Sealer {
    private const val STORE = "AndroidKeyStore"
    private const val ALIAS = "opus_car_token"
    private const val CIPHER = "AES/GCM/NoPadding"
    private const val IV_BYTES = 12
    private const val TAG_BITS = 128

    override fun seal(plain: String): String = keystore {
        val cipher = Cipher.getInstance(CIPHER).apply { init(Cipher.ENCRYPT_MODE, sealingKey()) }
        Base64.encodeToString(cipher.iv + cipher.doFinal(plain.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
    }

    override fun open(sealed: String): String {
        val bytes = try {
            Base64.decode(sealed, Base64.NO_WRAP)
        } catch (malformed: IllegalArgumentException) {
            throw SealBroken("the sealed token is not base64", malformed)
        }
        if (bytes.size <= IV_BYTES) throw SealBroken("the sealed token is too short to hold anything")
        return keystore {
            val key = store().getKey(ALIAS, null) as SecretKey? ?: throw SealBroken("the key that sealed the token is gone")
            val cipher = Cipher.getInstance(CIPHER).apply {
                init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(TAG_BITS, bytes, 0, IV_BYTES))
            }
            String(cipher.doFinal(bytes, IV_BYTES, bytes.size - IV_BYTES), Charsets.UTF_8)
        }
    }

    /** A seal replaces whatever the old key held, so a key that cannot be
     *  loaded is dropped here instead of failing every pairing after it. */
    private fun sealingKey(): SecretKey {
        val store = store()
        try {
            (store.getKey(ALIAS, null) as SecretKey?)?.let { return it }
        } catch (unusable: UnrecoverableKeyException) {
            store.deleteEntry(ALIAS)
        }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, STORE).apply {
            init(
                KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build()
            )
        }.generateKey()
    }

    private fun store(): KeyStore = KeyStore.getInstance(STORE).apply { load(null) }

    private inline fun <T> keystore(work: () -> T): T =
        try {
            work()
        } catch (broken: SealBroken) {
            throw broken
        } catch (failure: GeneralSecurityException) {
            throw judged(failure)
        } catch (failure: ProviderException) {
            throw judged(failure)
        } catch (failure: IOException) {
            throw SealUnavailable(failure)
        }

    private fun judged(failure: Exception): GeneralSecurityException {
        val gone = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && keystoreSaysGone(failure)
        return if (broken(failure, gone)) {
            SealBroken("the sealed token can never be opened again", failure)
        } else {
            SealUnavailable(failure)
        }
    }

    /** Only proof that the token is lost for good counts: the ciphertext does
     *  not belong to the key, the key was invalidated, or the keystore says the
     *  key is gone or corrupt. A keystore that is busy or restarting throws
     *  the same wrapper types, so everything else is worth asking again. */
    internal fun broken(failure: Throwable, keystoreSaysGone: Boolean): Boolean =
        keystoreSaysGone || generateSequence(failure) { it.cause }.any {
            it is AEADBadTagException || it is KeyPermanentlyInvalidatedException
        }

    @RequiresApi(Build.VERSION_CODES.TIRAMISU)
    private fun keystoreSaysGone(failure: Throwable): Boolean =
        generateSequence(failure) { it.cause }.filterIsInstance<KeystoreFailure>().any {
            it.numericErrorCode == KeystoreFailure.ERROR_KEY_DOES_NOT_EXIST ||
                it.numericErrorCode == KeystoreFailure.ERROR_KEY_CORRUPTED
        }
}
