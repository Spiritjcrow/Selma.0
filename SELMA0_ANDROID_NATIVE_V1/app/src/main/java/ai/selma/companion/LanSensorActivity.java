package ai.selma.companion;

import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.Enumeration;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Explicitly started LAN connectivity diagnostic. Not a packet sniffer or sensor-fusion engine. */
public final class LanSensorActivity extends Activity {
    private static final int PORT = 43871;
    private final ExecutorService workers = Executors.newCachedThreadPool();
    private volatile ServerSocket listener;
    private TextView status;
    private EditText peer, pairing, payload;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 24, 24, 24);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);
        status = new TextView(this);
        root.addView(status);
        peer = field(root, "Peer IPv4 address", "192.168.1.10");
        pairing = field(root, "Shared pairing phrase (set same on both devices)", "");
        payload = field(root, "Diagnostic message", "Hello from Selma");
        Button start = new Button(this);
        start.setText("Start receiving");
        root.addView(start);
        start.setOnClickListener(v -> startReceiver());
        Button send = new Button(this);
        send.setText("Send to peer");
        root.addView(send);
        send.setOnClickListener(v -> sendMessage());
        Button stop = new Button(this);
        stop.setText("Stop receiving");
        root.addView(stop);
        stop.setOnClickListener(v -> stopReceiver());
        report("LAN diagnostic. Port " + PORT + ". Local IPv4: " + localIp()
            + ". Both devices must be on a trusted network. No automatic discovery.");
    }

    private EditText field(LinearLayout parent, String hint, String value) {
        EditText edit = new EditText(this);
        edit.setHint(hint);
        edit.setSingleLine(true);
        edit.setText(value);
        parent.addView(edit);
        return edit;
    }

    private void startReceiver() {
        if (listener != null && !listener.isClosed()) { report("Already listening"); return; }
        final String secret = pairing.getText().toString();
        if (secret.length() < 12) { report("Use a pairing phrase of at least 12 characters"); return; }
        workers.execute(() -> {
            try (ServerSocket server = new ServerSocket(PORT)) {
                listener = server;
                report("Listening on " + localIp() + ":" + PORT);
                while (!server.isClosed()) {
                    try {
                        Socket client = server.accept();
                        workers.execute(() -> receive(client, secret));
                    } catch (Exception e) {
                        if (!server.isClosed()) report("Accept error: " + e.getClass().getSimpleName());
                    }
                }
            } catch (Exception e) { report("Receiver error: " + e.getClass().getSimpleName()); }
            finally { listener = null; }
        });
    }

    private void receive(Socket client, String secret) {
        try (Socket socket = client) {
            socket.setSoTimeout(4000);
            BufferedReader in = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
            String supplied = in.readLine();
            String message = in.readLine();
            if (secret.equals(supplied) && message != null && message.length() <= 2048) {
                report("Received from " + socket.getInetAddress().getHostAddress() + ": " + message);
            } else report("Rejected inbound message");
        } catch (Exception e) { report("Receive error: " + e.getClass().getSimpleName()); }
    }

    private void sendMessage() {
        String host = peer.getText().toString().trim();
        String secret = pairing.getText().toString();
        String message = payload.getText().toString();
        if (secret.length() < 12 || message.contains("\n") || message.contains("\r")
                || message.length() > 2048 || host.isEmpty()) {
            report("Check peer IP, pairing phrase (12+), and single-line message"); return;
        }
        workers.execute(() -> {
            try (Socket socket = new Socket()) {
                socket.connect(new java.net.InetSocketAddress(host, PORT), 4000);
                socket.setSoTimeout(4000);
                OutputStreamWriter out = new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8);
                out.write(secret + "\n" + message + "\n");
                out.flush();
                report("Message sent to " + host + " (delivery not acknowledged)");
            } catch (Exception e) { report("Send error: " + e.getClass().getSimpleName()); }
        });
    }

    private String localIp() {
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces.hasMoreElements()) {
                NetworkInterface net = interfaces.nextElement();
                if (!net.isUp() || net.isLoopback()) continue;
                Enumeration<InetAddress> addresses = net.getInetAddresses();
                while (addresses.hasMoreElements()) {
                    InetAddress ip = addresses.nextElement();
                    if (ip instanceof java.net.Inet4Address && ip.isSiteLocalAddress())
                        return ip.getHostAddress();
                }
            }
        } catch (Exception ignored) { }
        return "unavailable";
    }

    private void stopReceiver() {
        ServerSocket server = listener;
        if (server != null) try { server.close(); } catch (Exception ignored) { }
        report("Receiver stopped");
    }

    private void report(String line) { runOnUiThread(() -> status.append(line + "\n")); }
    @Override protected void onDestroy() {
        stopReceiver();
        workers.shutdownNow();
        super.onDestroy();
    }
}
