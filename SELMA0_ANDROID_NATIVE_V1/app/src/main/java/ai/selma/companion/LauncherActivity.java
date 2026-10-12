package ai.selma.companion;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.GridLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextClock;
import android.widget.TextView;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Opt-in, rootless Android HOME activity. It never sets itself as the default
 * launcher, runs privileged commands, or silently starts a network service.
 */
public final class LauncherActivity extends Activity {
    private static final String PREFS = "selma_launcher_v1";
    private static final String PINNED = "pinned_packages";
    private static final String LIGHT = "light_mode";
    private static final String WORKSPACE_PREF = "workspace_assignments";
    private static final String[] WORKSPACE_NAMES = {"Build", "Connect", "Secure", "Daily"};
    private static final int MINT = Color.rgb(79, 232, 195);
    private static final int VIOLET = Color.rgb(167, 144, 253);
    private static final String LOCAL_ASSISTANT = "http://127.0.0.1:8765/";

    private final List<ResolveInfo> installed = new ArrayList<>();
    private LinearLayout screen;
    private LinearLayout main;
    private LinearLayout navigation;
    private LinearLayout workspaceNavigation;
    private SharedPreferences preferences;
    private Set<String> pinned;
    private final Map<String, String> assignments = new HashMap<>();
    private String activeWorkspace = "Build";
    private String section = "HOME";
    private String filter = "";
    private boolean light;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        preferences = getSharedPreferences(PREFS, MODE_PRIVATE);
        pinned = new HashSet<>(preferences.getStringSet(PINNED, Collections.emptySet()));
        light = preferences.getBoolean(LIGHT, false);
        for (String value : preferences.getStringSet(WORKSPACE_PREF, Collections.emptySet())) {
            int split = value.indexOf('|');
            if (split <= 0) continue;
            String category = value.substring(split + 1);
            for (String allowed : WORKSPACE_NAMES) {
                if (allowed.equals(category)) assignments.put(value.substring(0, split), category);
            }
        }
        if (savedInstanceState != null) {
            String restored = savedInstanceState.getString("section", "HOME");
            if ("HOME".equals(restored) || "APPS".equals(restored)
                    || "WORKSPACES".equals(restored) || "SYSTEM".equals(restored)) section = restored;
            filter = savedInstanceState.getString("filter", "");
            String workspace = savedInstanceState.getString("workspace", "Build");
            for (String allowed : WORKSPACE_NAMES) {
                if (allowed.equals(workspace)) activeWorkspace = workspace;
            }
        }
        loadApps();
        createShell();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putString("section", section);
        state.putString("filter", filter);
        state.putString("workspace", activeWorkspace);
        super.onSaveInstanceState(state);
    }

    @Override public void onBackPressed() {
        if (!"HOME".equals(section)) {
            section = "HOME";
            filter = "";
            showSection();
        } else {
            // A HOME activity should not disappear on a Back gesture.
        }
    }

    @Override protected void onResume() {
        super.onResume();
        if (main != null) {
            loadApps();
            showSection();
        }
    }

    private int background() { return light ? Color.rgb(246, 248, 250) : Color.rgb(12, 16, 28); }
    private int surface() { return light ? Color.WHITE : Color.rgb(24, 30, 47); }
    private int foreground() { return light ? Color.rgb(21, 33, 48) : Color.rgb(238, 243, 251); }
    private int muted() { return light ? Color.rgb(80, 93, 107) : Color.rgb(158, 174, 190); }
    private int dp(float size) { return (int) (getResources().getDisplayMetrics().density * size + 0.5f); }

    private GradientDrawable shape(int color, int radius) {
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(color);
        bg.setCornerRadius(dp(radius));
        return bg;
    }

    private TextView text(String label, int sp, int color, boolean bold) {
        TextView v = new TextView(this);
        v.setText(label);
        v.setTextSize(sp);
        v.setTextColor(color);
        if (bold) v.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        v.setGravity(Gravity.CENTER_VERTICAL);
        return v;
    }

    private LinearLayout vertical() {
        LinearLayout v = new LinearLayout(this);
        v.setOrientation(LinearLayout.VERTICAL);
        return v;
    }

    private LinearLayout row() {
        LinearLayout v = new LinearLayout(this);
        v.setOrientation(LinearLayout.HORIZONTAL);
        v.setGravity(Gravity.CENTER_VERTICAL);
        return v;
    }

    private void pad(View view, int a, int b) { view.setPadding(dp(a), dp(b), dp(a), dp(b)); }

    private LinearLayout.LayoutParams full(int top) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.topMargin = dp(top);
        return lp;
    }

    private LinearLayout panel() {
        LinearLayout v = vertical();
        pad(v, 16, 14);
        v.setBackground(shape(surface(), 20));
        return v;
    }

    private void createShell() {
        getWindow().setStatusBarColor(background());
        getWindow().setNavigationBarColor(background());
        screen = vertical();
        screen.setBackgroundColor(background());

        LinearLayout top = row();
        top.setPadding(dp(20), dp(14), dp(20), dp(10));
        LinearLayout identity = vertical();
        TextView name = text("SELMA OS", 16, foreground(), true);
        TextView tagline = text("Local first  •  User controlled", 11, muted(), false);
        identity.addView(name);
        identity.addView(tagline);
        top.addView(identity, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView orb = text("◉", 32, MINT, true);
        orb.setGravity(Gravity.CENTER);
        orb.setContentDescription("Open local Selma assistant");
        orb.setBackground(shape(surface(), 20));
        orb.setOnClickListener(v -> openLocalAssistant());
        top.addView(orb, new LinearLayout.LayoutParams(dp(58), dp(58)));
        screen.addView(top);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        main = vertical();
        main.setPadding(dp(16), 0, dp(16), dp(28));
        scroll.addView(main);
        screen.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1f));

        navigation = row();
        navigation.setPadding(dp(12), dp(9), dp(12), dp(14));
        navigation.setBackgroundColor(surface());
        screen.addView(navigation);
        setContentView(screen);
        showSection();
    }

    private void navItem(String label, String target) {
        TextView item = text(label, 14, section.equals(target) ? MINT : muted(), true);
        item.setGravity(Gravity.CENTER);
        item.setMinHeight(dp(52));
        item.setFocusable(true);
        item.setSelected(section.equals(target));
        item.setContentDescription(label + " tab");
        item.setOnClickListener(v -> {
            section = target;
            filter = "";
            showSection();
            focusSelectedNavigationItem();
        });
        navigation.addView(item, new LinearLayout.LayoutParams(0, dp(54), 1f));
    }

    private void focusSelectedNavigationItem() {
        for (int i = 0; i < navigation.getChildCount(); i++) {
            View child = navigation.getChildAt(i);
            if (child.isSelected()) {
                child.requestFocus();
                return;
            }
        }
    }

    private String sectionLabel() {
        if ("APPS".equals(section)) return "SelmaOS Applications";
        if ("WORKSPACES".equals(section)) return "SelmaOS Workspaces";
        if ("SYSTEM".equals(section)) return "SelmaOS System";
        return "SelmaOS Home";
    }

    private void showSection() {
        if (main == null) return;
        main.removeAllViews();
        navigation.removeAllViews();
        workspaceNavigation = null;
        if ("APPS".equals(section)) renderApps();
        else if ("WORKSPACES".equals(section)) renderWorkspaces();
        else if ("SYSTEM".equals(section)) renderSystem();
        else renderHome();
        main.setAccessibilityPaneTitle(sectionLabel());
        navItem("Home", "HOME");
        navItem("Apps", "APPS");
        navItem("Work", "WORKSPACES");
        navItem("System", "SYSTEM");
    }

    private void title(String title, String subtitle) {
        TextView h = text(title, 26, foreground(), true);
        h.setAccessibilityHeading(true);
        main.addView(h, full(18));
        TextView s = text(subtitle, 13, muted(), false);
        main.addView(s, full(5));
    }

    private void sectionTitle(String value) {
        TextView h = text(value, 17, foreground(), true);
        h.setAccessibilityHeading(true);
        main.addView(h, full(24));
    }

    private TextView action(String title, String description, Runnable run) {
        LinearLayout tile = panel();
        TextView h = text(title, 16, foreground(), true);
        TextView d = text(description, 12, muted(), false);
        tile.addView(h);
        tile.addView(d, full(5));
        tile.setMinimumHeight(dp(80));
        tile.setContentDescription(title + ". " + description);
        tile.setOnClickListener(v -> run.run());
        main.addView(tile, full(10));
        return h;
    }

    private void renderHome() {
        LinearLayout hero = panel();
        TextClock clock = new TextClock(this);
        clock.setFormat12Hour("h:mm");
        clock.setFormat24Hour("HH:mm");
        clock.setTextSize(40);
        clock.setTextColor(foreground());
        clock.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        hero.addView(clock);
        hero.addView(text(new SimpleDateFormat("EEEE, d MMMM", Locale.getDefault())
                .format(new Date()), 14, muted(), false), full(2));
        hero.addView(text("Ready whenever you are. Nothing runs without your say.", 13,
                MINT, false), full(12));
        main.addView(hero, full(14));

        sectionTitle("Your command surface");
        action("✦  Selma assistant", "Local voice/chat entry point · requires running local runtime",
                this::openLocalAssistant);
        action("⌕  All applications", "Search and launch apps installed on this device", () -> {
            section = "APPS";
            showSection();
        });
        action("▦  Workspaces", "Organize installed apps into Build, Connect, Secure and Daily", () -> {
            section = "WORKSPACES";
            showSection();
        });
        sectionTitle("Pinned workspace");
        List<ResolveInfo> favorites = new ArrayList<>();
        for (ResolveInfo item : installed) {
            if (pinned.contains(item.activityInfo.packageName)) favorites.add(item);
        }
        if (favorites.isEmpty()) {
            TextView hint = text("No pinned apps yet. Open Apps, then long-press an app to pin it here.",
                    13, muted(), false);
            main.addView(hint, full(10));
        } else {
            for (int i = 0; i < Math.min(favorites.size(), 6); i++) {
                addAppRow(favorites.get(i), main);
            }
        }
        sectionTitle("Quick access");
        action("⚙  System controls", "Wi-Fi, Bluetooth, settings, files and display", () -> {
            section = "SYSTEM";
            showSection();
        });
    }

    private void loadApps() {
        installed.clear();
        Intent intent = new Intent(Intent.ACTION_MAIN);
        intent.addCategory(Intent.CATEGORY_LAUNCHER);
        PackageManager pm = getPackageManager();
        installed.addAll(pm.queryIntentActivities(intent, 0));
        installed.removeIf(info -> info.activityInfo == null
                || getPackageName().equals(info.activityInfo.packageName));
        installed.sort(Comparator.comparing(x -> x.loadLabel(pm).toString().toLowerCase(Locale.ROOT)));
    }

    private void renderApps() {
        title("Applications", installed.size() + " discoverable entries · use ★ to pin or ⇄ to organize");
        EditText search = new EditText(this);
        search.setSingleLine(true);
        search.setTextSize(16);
        search.setHint("Search installed applications");
        search.setTextColor(foreground());
        search.setHintTextColor(muted());
        search.setBackground(shape(surface(), 18));
        search.setPadding(dp(16), 0, dp(16), 0);
        search.setMinHeight(dp(56));
        main.addView(search, full(18));
        LinearLayout results = vertical();
        main.addView(results, full(10));
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                filter = s.toString();
                displayApps(results, filter);
            }
            @Override public void afterTextChanged(Editable s) {}
        });
        search.setText(filter);
        search.setSelection(search.length());
        displayApps(results, filter);
        results.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    }

    private void displayApps(LinearLayout destination, String query) {
        destination.removeAllViews();
        String needle = query.trim().toLowerCase(Locale.ROOT);
        int matches = 0;
        for (ResolveInfo info : installed) {
            if (!info.loadLabel(getPackageManager()).toString()
                    .toLowerCase(Locale.ROOT).contains(needle)) continue;
            addAppRow(info, destination);
            matches++;
        }
        if (matches == 0) destination.addView(text("No matching launchable apps.", 14, muted(), false));
    }

    private void addAppRow(ResolveInfo info, LinearLayout destination) {
        PackageManager pm = getPackageManager();
        String pkg = info.activityInfo.packageName;
        String label = info.loadLabel(pm).toString();
        LinearLayout cell = row();
        cell.setPadding(dp(14), dp(10), dp(14), dp(10));
        cell.setBackground(shape(surface(), 16));
        ImageView icon = new ImageView(this);
        icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        try { icon.setImageDrawable(info.loadIcon(pm)); }
        catch (RuntimeException ignored) { icon.setImageResource(android.R.drawable.sym_def_app_icon); }
        cell.addView(icon, new LinearLayout.LayoutParams(dp(42), dp(42)));
        LinearLayout texts = vertical();
        texts.setPadding(dp(12), 0, 0, 0);
        texts.addView(text(label, 15, foreground(), true));
        TextView pinState = text(pinned.contains(pkg) ? "Pinned to Home" : "Tap ★ to pin to Home",
                11, muted(), false);
        texts.addView(pinState);
        cell.addView(texts, new LinearLayout.LayoutParams(0, -2, 1f));
        cell.setContentDescription(label + ", " + (pinned.contains(pkg) ? "pinned" : "not pinned"));
        cell.setOnClickListener(v -> launch(info));
        TextView pin = text("★", 21, pinned.contains(pkg) ? MINT : muted(), true);
        pin.setGravity(Gravity.CENTER);
        pin.setMinWidth(dp(48));
        pin.setMinHeight(dp(48));
        pin.setContentDescription((pinned.contains(pkg) ? "Unpin " : "Pin ") + label);
        pin.setOnClickListener(v -> {
            togglePinned(pkg, label);
            boolean isPinned = pinned.contains(pkg);
            pin.setTextColor(isPinned ? MINT : muted());
            pin.setContentDescription((isPinned ? "Unpin " : "Pin ") + label);
            pinState.setText(isPinned ? "Pinned to Home" : "Tap ★ to pin to Home");
            cell.setContentDescription(label + ", " + (isPinned ? "pinned" : "not pinned"));
        });
        cell.setOnLongClickListener(v -> {
            pin.performClick();
            return true;
        });
        cell.addView(pin, new LinearLayout.LayoutParams(dp(48), dp(48)));
        TextView organize = text("⇄", 20, MINT, true);
        organize.setGravity(Gravity.CENTER);
        organize.setMinWidth(dp(48));
        organize.setMinHeight(dp(48));
        organize.setContentDescription("Choose workspace for " + label);
        organize.setOnClickListener(v -> chooseWorkspace(pkg, label));
        cell.addView(organize, new LinearLayout.LayoutParams(dp(48), dp(48)));
        destination.addView(cell, full(8));
    }

    private void togglePinned(String pkg, String label) {
        if (!pinned.add(pkg)) pinned.remove(pkg);
        preferences.edit().putStringSet(PINNED, new HashSet<>(pinned)).apply();
        Toast.makeText(this, label + (pinned.contains(pkg) ? " pinned" : " unpinned"),
                Toast.LENGTH_SHORT).show();
    }

    private void chooseWorkspace(String pkg, String label) {
        String[] choices = {"None", "Build", "Connect", "Secure", "Daily"};
        String current = assignments.get(pkg);
        int selected = 0;
        for (int i = 1; i < choices.length; i++) {
            if (choices[i].equals(current)) selected = i;
        }
        new AlertDialog.Builder(this)
                .setTitle("Workspace for " + label)
                .setSingleChoiceItems(choices, selected, (dialog, which) -> {
                    if (which == 0) assignments.remove(pkg);
                    else assignments.put(pkg, choices[which]);
                    Set<String> values = new HashSet<>();
                    for (Map.Entry<String, String> entry : assignments.entrySet()) {
                        values.add(entry.getKey() + "|" + entry.getValue());
                    }
                    preferences.edit().putStringSet(WORKSPACE_PREF, values).apply();
                    dialog.dismiss();
                    showSection();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void renderWorkspaces() {
        title("Workspaces", "Local app collections; nothing is installed or connected automatically");
        LinearLayout choices = row();
        workspaceNavigation = choices;
        for (String group : WORKSPACE_NAMES) {
            TextView select = text(group, 12, group.equals(activeWorkspace) ? background() : foreground(), true);
            select.setGravity(Gravity.CENTER);
            select.setMinHeight(dp(48));
            select.setFocusable(true);
            select.setBackground(shape(group.equals(activeWorkspace) ? MINT : surface(), 14));
            select.setSelected(group.equals(activeWorkspace));
            select.setContentDescription(group + " workspace");
            select.setOnClickListener(v -> {
                activeWorkspace = group;
                showSection();
                focusSelectedWorkspaceItem();
            });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(48), 1f);
            lp.setMargins(dp(2), 0, dp(2), 0);
            choices.addView(select, lp);
        }
        main.addView(choices, full(20));
        sectionTitle(activeWorkspace);
        int count = 0;
        for (ResolveInfo info : installed) {
            if (activeWorkspace.equals(assignments.get(info.activityInfo.packageName))) {
                addAppRow(info, main);
                count++;
            }
        }
        if (count == 0) {
            TextView message = text("No apps assigned. Open Apps, tap ⇄ next to an installed app, and choose "
                    + activeWorkspace + ".", 14, muted(), false);
            main.addView(message, full(14));
            action("Find apps", "Choose from the apps already on this device", () -> {
                section = "APPS";
                showSection();
            });
        }
    }

    private void focusSelectedWorkspaceItem() {
        if (workspaceNavigation == null) return;
        for (int i = 0; i < workspaceNavigation.getChildCount(); i++) {
            View child = workspaceNavigation.getChildAt(i);
            if (child.isSelected()) {
                child.requestFocus();
                return;
            }
        }
    }

    private void launch(ResolveInfo info) {
        try {
            Intent run = new Intent(Intent.ACTION_MAIN);
            run.addCategory(Intent.CATEGORY_LAUNCHER);
            run.setComponent(new ComponentName(
                    info.activityInfo.packageName, info.activityInfo.name));
            run.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            startActivity(run);
        } catch (ActivityNotFoundException | SecurityException e) {
            Toast.makeText(this, "This app cannot be opened on this device", Toast.LENGTH_LONG).show();
        }
    }

    private void safeActivity(Intent intent, String unavailable) {
        try { startActivity(intent); }
        catch (ActivityNotFoundException | SecurityException e) {
            Toast.makeText(this, unavailable, Toast.LENGTH_LONG).show();
        }
    }

    private void openLocalAssistant() {
        safeActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(LOCAL_ASSISTANT)),
                "No browser found. Start the local Selma runtime first.");
    }

    private void renderSystem() {
        title("System & tools", "Rootless controls · Android permissions stay in charge");
        sectionTitle("Device");
        action("Wi-Fi connection", "Open the official Android connectivity panel", () -> {
            String target = Build.VERSION.SDK_INT >= 29
                    ? Settings.Panel.ACTION_WIFI : Settings.ACTION_WIFI_SETTINGS;
            safeActivity(new Intent(target), "Wi-Fi settings unavailable");
        });
        action("Bluetooth", "Official Android Bluetooth settings",
                () -> safeActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS),
                        "Bluetooth settings unavailable"));
        action("System settings", "Device preferences, security and accessibility",
                () -> safeActivity(new Intent(Settings.ACTION_SETTINGS), "Settings unavailable"));
        action("Files", "Choose a file through Android's protected document picker", () -> {
            Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            picker.addCategory(Intent.CATEGORY_OPENABLE);
            picker.setType("*/*");
            safeActivity(picker, "Document picker unavailable");
        });
        sectionTitle("Selma controls");
        action("Local assistant", "Open 127.0.0.1:8765; no public network binding",
                this::openLocalAssistant);
        action("Cloud companion", "Optional existing HTTPS Selma companion", () ->
                safeActivity(new Intent(this, MainActivity.class),
                        "Cloud companion unavailable"));
        action("Appearance", light ? "Switch to high-contrast dark surface" : "Switch to light surface", () -> {
            light = !light;
            preferences.edit().putBoolean(LIGHT, light).apply();
            createShell();
        });
        action("Home app", "Choose your default HOME app in Android settings",
                () -> safeActivity(new Intent(Settings.ACTION_HOME_SETTINGS),
                        "Default launcher settings unavailable"));
        TextView note = text("SelmaOS cannot silently enable root, change Wi-Fi credentials, "
                + "read notifications, control other apps, or bypass Android device policy. "
                + "Extra capabilities require their own permissions and verified adapters.",
                12, muted(), false);
        main.addView(note, full(20));
    }
}



