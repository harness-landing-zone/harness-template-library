package demo;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class GreetingTest {
    @Test void greetsWorldByDefault() {
        assertEquals("Hello, World!", Greeting.message(null));
    }
    @Test void handlesBlankNames() {
        assertEquals("Hello, World!", Greeting.message("  "));
    }
    @Test void greetsNamedPerson() {
        assertEquals("Hello, Harness!", Greeting.message(" Harness "));
    }
}
