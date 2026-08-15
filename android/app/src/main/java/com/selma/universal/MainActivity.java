package com.selma.universal;
import android.Manifest; import android.app.Activity; import android.content.*; import android.net.Uri; import android.os.*; import android.provider.Settings; import android.widget.TextView; import androidx.core.content.ContextCompat;
public class MainActivity extends Activity {
 TextView status;
 public void onCreate(Bundle b){super.onCreate(b);setContentView(R.layout.activity_main);status=findViewById(R.id.status);status.setText("Selma Universal Native\n"+DeviceProfile.detect(this).summary());if(Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},31);findViewById(R.id.start).setOnClickListener(v->startSelma());findViewById(R.id.stop).setOnClickListener(v->stopService(new Intent(this,SelmaOverlayService.class)));}
 void startSelma(){if(Build.VERSION.SDK_INT>=23&&!Settings.canDrawOverlays(this)){startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,Uri.parse("package:"+getPackageName())));status.setText("Grant Draw over other apps, return, then press Start.");return;}Intent i=new Intent(this,SelmaOverlayService.class);if(Build.VERSION.SDK_INT>=26)ContextCompat.startForegroundService(this,i);else startService(i);status.setText("Selma started with automatic device fallback.");}
}
