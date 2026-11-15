package ai.selma.companion;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.telephony.euicc.EuiccManager;

/**
 * Read-only eSIM capability detection and an explicitly user-triggered
 * transition to Android's own embedded-SIM management screen.
 *
 * Does not read EIDs/ICCIDs, request carrier privileges, download profiles,
 * toggle subscriptions, or manage credentials.
 */
public final class EsimCapability {
    private EsimCapability() { }

    public enum Status {
        OS_UNSUPPORTED,
        HARDWARE_UNSUPPORTED,
        SERVICE_UNAVAILABLE,
        EMBEDDED_SUBSCRIPTIONS_DISABLED,
        SYSTEM_MANAGEMENT_AVAILABLE
    }

    public static Status inspect(Context context) {
        if (context == null) {
            throw new IllegalArgumentException("context is required");
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) {
            return Status.OS_UNSUPPORTED;
        }
        PackageManager manager = context.getPackageManager();
        if (manager == null ||
                !manager.hasSystemFeature(PackageManager.FEATURE_TELEPHONY_EUICC)) {
            return Status.HARDWARE_UNSUPPORTED;
        }
        try {
            EuiccManager euicc =
                    (EuiccManager) context.getSystemService(Context.EUICC_SERVICE);
            if (euicc == null) {
                return Status.SERVICE_UNAVAILABLE;
            }
            return euicc.isEnabled()
                    ? Status.SYSTEM_MANAGEMENT_AVAILABLE
                    : Status.EMBEDDED_SUBSCRIPTIONS_DISABLED;
        } catch (SecurityException | UnsupportedOperationException exception) {
            return Status.SERVICE_UNAVAILABLE;
        }
    }

    /**
     * This must only be invoked in response to an explicit user action.
     * A successful return means Android accepted an intent, not that a
     * subscription was installed or changed.
     */
    public static boolean openSystemManagement(Activity activity) {
        if (activity == null ||
                inspect(activity) != Status.SYSTEM_MANAGEMENT_AVAILABLE) {
            return false;
        }
        Intent intent = new Intent(EuiccManager.ACTION_MANAGE_EMBEDDED_SUBSCRIPTIONS);
        if (intent.resolveActivity(activity.getPackageManager()) == null) {
            return false;
        }
        try {
            activity.startActivity(intent);
            return true;
        } catch (SecurityException | android.content.ActivityNotFoundException exception) {
            return false;
        }
    }
}
