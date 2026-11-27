package org.selma.home;
import android.service.dreams.DreamService;
public class ToasterDream extends DreamService {
    public void onAttachedToWindow(){super.onAttachedToWindow();setFullscreen(true);setInteractive(false);android.view.View blank=new android.view.View(this);blank.setBackgroundColor(android.graphics.Color.BLACK);setContentView(blank);}
}
