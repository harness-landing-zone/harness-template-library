package demo;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.assertEquals;

class AppTest {
    static HttpServer server;
    static HttpClient client;

    @BeforeAll static void start() throws Exception {
        server = App.start(0);
        client = HttpClient.newHttpClient();
    }
    @AfterAll static void stop() {
        client.close();
        server.stop(0);
    }
    HttpResponse<String> get(String path) throws Exception {
        var url = URI.create("http://127.0.0.1:" + server.getAddress().getPort() + path);
        return client.send(HttpRequest.newBuilder(url).timeout(Duration.ofSeconds(5)).build(),
                HttpResponse.BodyHandlers.ofString());
    }
    @Test void homepageGreetsWorld() throws Exception {
        var response = get("/");
        assertEquals(200, response.statusCode());
        assertEquals("Hello, World!", response.body());
    }
    @Test void healthEndpointIsReady() throws Exception {
        var response = get("/health");
        assertEquals(200, response.statusCode());
        assertEquals("OK", response.body());
    }
    @Test void unknownRouteReturns404() throws Exception {
        assertEquals(404, get("/missing").statusCode());
    }
}
