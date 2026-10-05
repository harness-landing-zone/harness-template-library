package demo;

public class Greeting {
    public static String message(String name) {
        return "Hello, " + (name == null || name.isBlank() ? "World" : name.strip()) + "!";
    }
}
