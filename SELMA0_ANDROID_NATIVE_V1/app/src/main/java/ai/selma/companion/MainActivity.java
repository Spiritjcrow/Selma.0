package ai.selma.companion;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;

public final class MainActivity extends Activity {
    private static final Uri SELMA_URL =
            Uri.parse("https://selma-official-companion.spiritjcrow1990.chatgpt.site");

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_main);
        findViewById(R.id.open_browser).setOnClickListener(view -> openCompanion());
    }

    private void openCompanion() {
        View browserError = findViewById(R.id.browser_error);
        browserError.setVisibility(View.GONE);
        Intent intent = new Intent(Intent.ACTION_VIEW, SELMA_URL);
        intent.addCategory(Intent.CATEGORY_BROWSABLE);
        try {
            startActivity(intent);
        } catch (ActivityNotFoundException error) {
            browserError.setVisibility(View.VISIBLE);
        }
    }
}
