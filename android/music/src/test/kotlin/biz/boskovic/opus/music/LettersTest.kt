package biz.boskovic.opus.music

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class LettersTest {
    private fun files(vararg pairs: Pair<String, String>) =
        pairs.forEach { (name, letter) -> assertEquals(letter, MusicTree.initial(name), name) }

    @Test
    fun `the Croatian letters are folders of their own`() {
        files(
            "Čola" to "Č",
            "ćiro" to "Ć",
            "Đorđe Balašević" to "Đ",
            "Šaban Šaulić" to "Š",
            "Željko Joksimović" to "Ž",
        )
    }

    @Test
    fun `the digraphs are single letters, written as a digraph is`() {
        files(
            "Džentlmeni" to "Dž",
            "DŽENTLMENI" to "Dž",
            "Ljuba Ninković" to "Lj",
            "LJUBAV" to "Lj",
            "Njonja" to "Nj",
        )
    }

    @Test
    fun `a letter that only looks like a digraph start is the plain letter`() {
        files(
            "Dino Merlin" to "D",
            "Lana Del Rey" to "L",
            "Nina Badrić" to "N",
            "Dzeko" to "D",
        )
    }

    @Test
    fun `a foreign accent files under the letter beneath it`() {
        files(
            "Édith Piaf" to "E",
            "Öystein Sunde" to "O",
            "Ñu" to "N",
            "Ångström" to "A",
        )
    }

    @Test
    fun `a name spelled with combining marks files the same as a composed one`() {
        files("Čola" to "Č", "Dž" to "Dž", "Željko" to "Ž")
    }

    @Test
    fun `digits and punctuation file under the hash`() {
        files(
            "2Cellos" to "#",
            "50 Cent" to "#",
            "!!!" to "#",
            "(hed) p.e." to "#",
            "" to "#",
            "   " to "#",
        )
    }

    @Test
    fun `a script the alphabet does not hold files under the question mark`() {
        files(
            "Бијело дугме" to "?",
            "Ελένη" to "?",
            "坂本龍一" to "?",
        )
    }

    @Test
    fun `leading whitespace is not a letter`() {
        files("  Arsen Dedić" to "A", "\tŠtulić" to "Š")
    }
}
