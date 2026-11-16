package ai.selma.companion;

import android.app.Activity;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.os.Bundle;
import android.content.Context;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.Map;

/** Read-only USB enumeration. Does not open interfaces, request ADB, or alter a target. */
public final class RescueHostActivity extends Activity {
    private TextView results;
    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        layout.setPadding(pad, pad, pad, pad);
        TextView heading = new TextView(this);
        heading.setText("Selma RescueHost | Read-only USB diagnostic");
        heading.setTextSize(20);
        layout.addView(heading);
        Button refresh = new Button(this);
        refresh.setText("Scan connected USB devices");
        layout.addView(refresh);
        ScrollView scroll = new ScrollView(this);
        results = new TextView(this);
        results.setTextIsSelectable(true);
        scroll.addView(results);
        layout.addView(scroll);
        setContentView(layout);
        refresh.setOnClickListener(v -> scan());
        scan();
    }
    private void scan() {
        UsbManager manager = (UsbManager) getSystemService(Context.USB_SERVICE);
        if (manager == null) {
            results.setText("USB service unavailable.");
            return;
        }
        Map<String, UsbDevice> devices = manager.getDeviceList();
        if (devices.isEmpty()) {
            results.setText("No USB peripheral detected. The host phone must support USB OTG; use a data-capable cable. A charging connection alone is not enough.");
            return;
        }
        StringBuilder output = new StringBuilder();
        output.append("Detected peripherals: ").append(devices.size()).append("\n\n");
        for (UsbDevice device : devices.values()) {
            output.append("Device: ").append(device.getDeviceName()).append("\n")
                .append("Vendor ID: ").append(device.getVendorId()).append("\n")
                .append("Product ID: ").append(device.getProductId()).append("\n")
                .append("USB class: ").append(device.getDeviceClass()).append("\n")
                .append("USB subclass: ").append(device.getDeviceSubclass()).append("\n")
                .append("Interfaces: ").append(device.getInterfaceCount()).append("\n")
                .append("Permission granted: ").append(manager.hasPermission(device)).append("\n\n");
        }
        output.append("Read-only scan complete. No unlock, firmware flash, or network change performed.");
        results.setText(output.toString());
    }
}
