package com.selma.universal;
import android.app.ActivityManager; import android.content.Context; import android.content.pm.*; import android.os.Build;
public final class DeviceProfile {
 public final boolean lowRam, hasGles2; public final int api, quality;
 private DeviceProfile(int a,boolean l,boolean g){api=a;lowRam=l;hasGles2=g;quality=l?0:1;}
 public static DeviceProfile detect(Context c){ActivityManager am=(ActivityManager)c.getSystemService(Context.ACTIVITY_SERVICE);boolean low=Build.VERSION.SDK_INT>=19&&am.isLowRamDevice();ConfigurationInfo i=am.getDeviceConfigurationInfo();boolean g=i!=null&&i.reqGlEsVersion>=0x00020000;return new DeviceProfile(Build.VERSION.SDK_INT,low,g);}
 public String summary(){return "API "+api+" | lowRAM="+lowRam+" | GLES2="+hasGles2;}
}
