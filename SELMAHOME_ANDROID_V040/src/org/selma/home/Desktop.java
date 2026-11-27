package org.selma.home;

import android.app.AlertDialog;
import android.content.*;
import android.content.pm.*;
import android.graphics.*;
import android.graphics.drawable.*;
import android.os.Bundle;
import android.provider.Settings;
import android.text.*;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import java.util.*;
import java.io.*;

public class Desktop extends Home {
    static final int INK=0xff18202a, PANEL=0xff252e39, GOLD=0xff97c6ee;
    FrameLayout desk;
    android.media.SoundPool sounds;int woo;long lastWoo;
    ImageView paper;TapEffects effects;ScrollView creative;float touchX,touchY;
    LinearLayout tasks,dock,menu,entries;
    EditText search;
    TextView start;
    boolean all;
    final Map<String,Pane> panes=new LinkedHashMap<>();
    final List<App> catalog=new ArrayList<>();

    public void onCreate(Bundle saved){
        super.onCreate(saved);
        LinearLayout root=column();
        root.setBackgroundColor(INK);
        root.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());return i;});
        desk=new FrameLayout(this);root.addView(desk,new LinearLayout.LayoutParams(-1,0,1));
        paper=new ImageView(this);paper.setScaleType(ImageView.ScaleType.CENTER_CROP);paper.setBackgroundColor(0xff18232f);desk.addView(paper);if(prefs.getBoolean("desktopPhoto",false))loadWallpaper();
        addShortcuts();
        paper.setOnClickListener(v->dismissMenu());
        paper.setOnLongClickListener(v->{popup(v,new String[]{"Start menu","Control Panel"},i->{if(i==0)openMenu();else open("Control Panel");});return true;});
        dock=row();dock.setBackgroundColor(0xff19161e);root.addView(dock,-1,dp(54));
        start=action(dock,"Start",()->{if(menu==null)openMenu();else dismissMenu();});
        String resourcesPackage=getResources().getResourcePackageName(getApplicationInfo().icon);
        int patch=getResources().getIdentifier("start_patch","drawable",resourcesPackage);
        if(patch!=0)start.setCompoundDrawablesWithIntrinsicBounds(getResources().getDrawable(patch,getTheme()),null,null,null);
        start.setTextColor(prefs.getInt("accent",GOLD));
        start.setOnLongClickListener(v->{notice("Hell · Employee entrance");return true;});
        sounds=new android.media.SoundPool.Builder().setMaxStreams(1).setAudioAttributes(new android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_ASSISTANCE_SONIFICATION).build()).build();
        int wooResource=getResources().getIdentifier("woo","raw",resourcesPackage);
        if(wooResource!=0)woo=sounds.load(this,wooResource,1);
        HorizontalScrollView taskStrip=new HorizontalScrollView(this);taskStrip.setHorizontalScrollBarEnabled(false);tasks=row();taskStrip.addView(tasks);dock.addView(taskStrip,new LinearLayout.LayoutParams(0,-1,1));
        TextClock clock=new TextClock(this);clock.setPadding(dp(6),0,dp(8),0);dock.addView(clock);
        TextView edit=action(dock,"✧",this::toggleCreative);edit.setContentDescription("Creative Mode");
        FrameLayout stack=new FrameLayout(this);stack.addView(root);effects=new TapEffects(this);stack.addView(effects);setContentView(stack);
        if(saved!=null)desk.post(()->{for(String name:new String[]{"Studio","Workbench","MCP tools","Control Panel"})if(saved.containsKey(name)){open(name);Pane p=panes.get(name);p.layout(saved.getInt(name));p.setVisibility(saved.getBoolean(name+"Shown")?View.VISIBLE:View.GONE);}});
    }
    void addShortcuts(){
        LinearLayout grid=column();grid.setPadding(dp(10),dp(12),0,0);
        LinearLayout upper=row(),lower=row();grid.addView(upper);grid.addView(lower);
        shortcut(upper,"Applications","desk_apps",()->{openMenu();all=true;fill();});
        shortcut(upper,"Workbench","desk_work",()->open("Workbench"));
        shortcut(lower,"MCP tools","desk_mcp",()->open("MCP tools"));
        shortcut(lower,"Studio","desk_studio",()->open("Studio"));
        desk.addView(grid,new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.LEFT));
    }
    void shortcut(LinearLayout row,String title,String icon,Runnable click){
        TextView v=text(title,13);v.setGravity(Gravity.CENTER);v.setFocusable(true);
        int id=getResources().getIdentifier(icon,"drawable",getResources().getResourcePackageName(getApplicationInfo().icon));
        v.setCompoundDrawablesWithIntrinsicBounds(0,id,0,0);v.setCompoundDrawablePadding(dp(4));v.setPadding(0,dp(8),0,0);
        v.setOnClickListener(view->click.run());row.addView(v,dp(92),dp(80));
    }
    TextView mcpStatus;
    @Override void serverChanged(){super.serverChanged();if(mcpStatus!=null)mcpStatus.setText(server==null?"Local server stopped":"Local server running");}
    View mcpTools(){
        LinearLayout l=column();l.setPadding(dp(16),dp(8),dp(16),dp(8));
        mcpStatus=text("",16);serverChanged();l.addView(mcpStatus);
        action(l,"Start server / connection details",()->{if(server==null)switchServer();else showConnection();});
        action(l,"Stop server",this::stopServer);
        action(l,"Open project Workbench",()->open("Workbench"));
        l.addView(text("Available tools",15));for(String tool:ToolServer.WORK)l.addView(text(tool,14));l.addView(text("story_complete",14));
        ScrollView sc=new ScrollView(this);sc.addView(l);return sc;
    }
    protected void onSaveInstanceState(Bundle b){super.onSaveInstanceState(b);for(Pane p:panes.values()){b.putInt(p.title,p.mode);b.putBoolean(p.title+"Shown",p.isShown());}}
    protected void onNewIntent(Intent intent){super.onNewIntent(intent);dismissMenu();for(Pane p:panes.values())p.setVisibility(View.GONE);}
    LinearLayout column(){LinearLayout l=new LinearLayout(this);l.setOrientation(1);return l;}
    LinearLayout row(){LinearLayout l=new LinearLayout(this);l.setGravity(Gravity.CENTER_VERTICAL);return l;}
    TextView text(String s,int size){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(0xfff6eff3);t.setGravity(Gravity.CENTER_VERTICAL);return t;}
    TextView action(LinearLayout parent,String name,Runnable click){TextView t=text(name,15);t.setPadding(dp(9),0,dp(9),0);t.setMinHeight(dp(48));t.setFocusable(true);t.setOnClickListener(v->click.run());parent.addView(t);return t;}
    GradientDrawable plate(int color){GradientDrawable g=new GradientDrawable();g.setColor(color);g.setCornerRadius(dp(12));g.setStroke(dp(1),0xff62505f);return g;}
    void popup(View anchor,String[] choices,java.util.function.IntConsumer select){PopupMenu p=new PopupMenu(this,anchor);for(int i=0;i<choices.length;i++)p.getMenu().add(0,i,i,choices[i]);p.setOnMenuItemClickListener(item->{select.accept(item.getItemId());return true;});p.show();}
    class App {
        ComponentName component;String title,key;ResolveInfo info;
        App(ResolveInfo r){info=r;component=new ComponentName(r.activityInfo.packageName,r.activityInfo.name);key=component.flattenToString();title=r.loadLabel(getPackageManager()).toString();}
    }
    void openMenu(){
        dismissMenu();catalog.clear();Intent q=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        for(ResolveInfo r:getPackageManager().queryIntentActivities(q,0))if(!getPackageName().equals(r.activityInfo.packageName))catalog.add(new App(r));
        catalog.sort((a,b)->a.title.compareToIgnoreCase(b.title));
        menu=column();menu.setFocusableInTouchMode(true);menu.setBackground(plate(PANEL));menu.setElevation(dp(9));menu.setPadding(dp(12),dp(6),dp(12),dp(6));
        FrameLayout.LayoutParams f=new FrameLayout.LayoutParams(Math.min(dp(410),desk.getWidth()-dp(12)),Math.min(dp(550),desk.getHeight()-dp(12)),Gravity.BOTTOM|Gravity.LEFT);f.setMargins(dp(6),0,0,dp(5));desk.addView(menu,f);
        search=new EditText(this);search.setSingleLine();search.setHint("Search apps");menu.addView(search,-1,dp(48));menu.requestFocus();
        LinearLayout tabs=row();menu.addView(tabs);all=false;action(tabs,"Pinned & recent",()->{all=false;search.setText("");fill();});action(tabs,"All apps",()->{all=true;search.setText("");fill();});
        ScrollView sc=new ScrollView(this);entries=column();sc.addView(entries);menu.addView(sc,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout foot=row();menu.addView(foot);action(foot,"Control Panel",()->open("Control Panel"));action(foot,"Power",()->new AlertDialog.Builder(this).setTitle("Device power").setMessage("Use your phone’s system power menu to restart or shut down.").setPositiveButton("Done",null).show());
        search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int n){}public void afterTextChanged(Editable e){}public void onTextChanged(CharSequence s,int a,int b,int c){fill();}});fill();
    }
    void dismissMenu(){if(menu!=null){((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(search.getWindowToken(),0);desk.removeView(menu);menu=null;}}
    void heading(String s){TextView h=text(s,13);h.setTextColor(GOLD);entries.addView(h);}
    void fill(){if(menu==null)return;entries.removeAllViews();String query=search.getText().toString().trim().toLowerCase(Locale.ROOT);
        boolean browse=all||!query.isEmpty();
        if(!browse)heading("Pinned");
        for(String n:new String[]{"Studio","Workbench","MCP tools","Control Panel"})if(n.toLowerCase(Locale.ROOT).contains(query))action(entries,n,()->open(n));
        for(App a:catalog)if((browse||prefs.getBoolean("pin:"+a.key,false))&&a.title.toLowerCase(Locale.ROOT).contains(query))appRow(a);
        if(!browse){ArrayList<App> recent=new ArrayList<>(catalog);recent.sort((a,b)->Long.compare(last(b),last(a)));int count=0;for(App a:recent){if(last(a)==0||count==5)break;if(count++==0)heading("Recent");appRow(a);}}
        if(query.equals("dealership"))action(entries,"D.P. & Skeeter · shuttle arrived",()->notice("Lunar relay connected"));
        if(entries.getChildCount()==0)heading("No matching apps");
    }
    long last(App a){return prefs.getLong("last:"+a.key,0);}
    void appRow(App a){TextView t=action(entries,a.title,()->{try{startActivity(Intent.makeMainActivity(a.component));prefs.edit().putLong("last:"+a.key,System.currentTimeMillis()).apply();dismissMenu();}catch(RuntimeException e){problem("App unavailable");}});
        Drawable icon=a.info.loadIcon(getPackageManager());icon.setBounds(0,0,dp(29),dp(29));t.setCompoundDrawables(icon,null,null,null);t.setCompoundDrawablePadding(dp(10));
        t.setOnLongClickListener(v->{boolean pinned=prefs.getBoolean("pin:"+a.key,false);popup(v,new String[]{pinned?"Unpin from Start":"Pin to Start","App info"},i->{if(i==0){prefs.edit().putBoolean("pin:"+a.key,!pinned).apply();fill();}else system(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:"+a.component.getPackageName())));});return true;});
    }
    SharedPreferences jobs(){return getSharedPreferences("workbench",0);}
    android.app.job.JobScheduler scheduler(){return getSystemService(android.app.job.JobScheduler.class);}
    void schedule(boolean daily){
        if(!daily){try{notice(workbenchTool("review_run"));}catch(IOException e){problem(e.getMessage());}return;}
        if(jobs().getString("tree","").isEmpty()){notice("Choose a project folder first");return;}
        android.app.job.JobInfo.Builder b=new android.app.job.JobInfo.Builder(daily?ReviewJob.DAILY:ReviewJob.MANUAL,new ComponentName(this,ReviewJob.class));
        if(daily)b.setPeriodic(86400000L).setPersisted(true);else b.setOverrideDeadline(0);
        if(scheduler().schedule(b.build())==android.app.job.JobScheduler.RESULT_SUCCESS){if(!daily)jobs().edit().putString("status","Queued").apply();notice(daily?"Daily review scheduled":"Review queued");}else problem("Android declined scheduling");
    }
    View workbench(){
        ScrollView sc=new ScrollView(this);LinearLayout l=column();sc.addView(l);l.setPadding(dp(12),dp(8),dp(12),dp(8));
        action(l,"Choose project folder",()->startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION),71));
        action(l,"Create Python foundation…",()->new AlertDialog.Builder(this).setTitle("Create a new project").setMessage("Select a parent folder. Selma will create a uniquely named subfolder with a working inventory CLI, unit tests and a build check.").setNegativeButton("Cancel",null).setPositiveButton("Choose folder",(d,w)->startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE),72)).show());
        EditText focus=new EditText(this);focus.setSingleLine();focus.setHint("Focus keyword, e.g. retry");focus.setText(jobs().getString("focus",""));l.addView(focus);
        action(l,"Save review focus",()->{jobs().edit().putString("focus",focus.getText().toString().trim()).apply();notice("Focus saved");});
        action(l,"Run project review",()->schedule(false));
        action(l,"Schedule daily review",()->schedule(true));
        action(l,"Cancel daily schedule",()->{scheduler().cancel(ReviewJob.DAILY);notice("Daily schedule canceled");});
        TextView report=text("",14);report.setTextIsSelectable(true);
        Runnable refresh=()->{String status=jobs().getString("status","No runs yet");String body="";
            android.util.AtomicFile f=new android.util.AtomicFile(new File(getFilesDir(),"review.txt"));
            try{body=new String(f.readFully(),java.nio.charset.StandardCharsets.UTF_8);}catch(IOException ignored){}
            report.setText(status+"\nDaily schedule: "+(scheduler().getPendingJob(ReviewJob.DAILY)==null?"off":"on")+"\n"+jobs().getString("tree","No folder selected")+"\n\n"+body);};
        action(l,"Refresh run report",refresh);l.addView(report);refresh.run();return sc;
    }
    protected void onActivityResult(int code,int status,Intent data){super.onActivityResult(code,status,data);
        if(code==73&&status==RESULT_OK&&data!=null&&data.getData()!=null){android.net.Uri uri=data.getData();try{getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);prefs.edit().putString("wallUri",uri.toString()).apply();loadWallpaper();}catch(Exception e){problem(e.getMessage());}}
        if(code==72&&status==RESULT_OK&&data!=null&&data.getData()!=null){android.net.Uri parent=data.getData();runTask(()->{try{android.net.Uri u=Foundation.create(this,parent);String msg="Created and verified "+u.getLastPathSegment();jobs().edit().putString("status",msg).apply();notice(msg);}catch(Exception e){problem(e.getMessage());}});}
        if(code==71&&status==RESULT_OK&&data!=null&&data.getData()!=null){try{
            android.net.Uri uri=data.getData();getContentResolver().takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION);
            String old=jobs().getString("tree","");jobs().edit().putString("tree",uri.toString()).apply();
            if(!old.isEmpty()&&!old.equals(uri.toString()))getContentResolver().releasePersistableUriPermission(android.net.Uri.parse(old),Intent.FLAG_GRANT_READ_URI_PERMISSION);
            notice("Project selected");}catch(SecurityException e){problem("Folder permission unavailable");}}}
    void busy(boolean value){if(effects!=null)effects.busy(value);}
    void problem(String message){runOnUiThread(()->{if(!isDestroyed()){if(effects!=null)effects.error(message);long now=android.os.SystemClock.uptimeMillis();if(sounds!=null&&now-lastWoo>1900&&prefs.getBoolean("sound",true)){sounds.play(woo,.55f,.55f,0,0,1);lastWoo=now;}notice(message==null?"Operation failed":message);}});}
    public boolean dispatchTouchEvent(MotionEvent e){if(e.getActionMasked()==MotionEvent.ACTION_DOWN){touchX=e.getRawX();touchY=e.getRawY();}
        if(effects!=null&&e.getActionMasked()==MotionEvent.ACTION_UP&&Math.hypot(touchX-e.getRawX(),touchY-e.getRawY())<dp(10)&&prefs.getBoolean("bursts",true)){int[] pos=new int[2];effects.getLocationOnScreen(pos);effects.burst(e.getRawX()-pos[0],e.getRawY()-pos[1]);}return super.dispatchTouchEvent(e);}
    void loadWallpaper(){String s=prefs.getString("wallUri","");if(s.isEmpty())return;try{android.graphics.ImageDecoder.Source source=android.graphics.ImageDecoder.createSource(getContentResolver(),android.net.Uri.parse(s));paper.setImageBitmap(android.graphics.ImageDecoder.decodeBitmap(source,(decoder,info,src)->{android.util.Size size=info.getSize();decoder.setTargetSampleSize(Math.max(1,(Math.max(size.getWidth(),size.getHeight())+2047)/2048));}));prefs.edit().putBoolean("desktopPhoto",true).apply();}catch(Exception e){paper.setImageDrawable(null);problem("Wallpaper unavailable");}}
    void toggleCreative(){if(creative!=null){desk.removeView(creative);creative=null;return;}dismissMenu();creative=new ScrollView(this);creative.setElevation(dp(14));creative.setBackground(plate(PANEL));LinearLayout l=column();l.setPadding(dp(12),0,dp(12),0);creative.addView(l);action(l,"Creative Mode   ×",this::toggleCreative);
        action(l,"Plain desktop",()->{paper.setImageDrawable(null);prefs.edit().putBoolean("desktopPhoto",false).apply();});action(l,"Choose wallpaper file…",()->startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("image/*"),73));

        action(l,"Cycle accent color",()->{int[] colors={0xffed67ca,0xff63ebdf,0xffefbb77};int i=prefs.getInt("accentIndex",0)+1;prefs.edit().putInt("accentIndex",i%3).putInt("accent",colors[i%3]).apply();start.setTextColor(colors[i%3]);paper.invalidate();});
        Switch sound=new Switch(this);sound.setText("Error woo");sound.setChecked(prefs.getBoolean("sound",true));sound.setOnCheckedChangeListener((v,b)->prefs.edit().putBoolean("sound",b).apply());l.addView(sound);
        Switch bursts=new Switch(this);bursts.setText("Tap creatures");bursts.setChecked(prefs.getBoolean("bursts",true));bursts.setOnCheckedChangeListener((v,b)->prefs.edit().putBoolean("bursts",b).apply());l.addView(bursts);
        FrameLayout.LayoutParams f=new FrameLayout.LayoutParams(Math.min(dp(240),desk.getWidth()),Math.min(dp(470),desk.getHeight()),Gravity.TOP|Gravity.RIGHT);desk.addView(creative,f);}
    void system(Intent intent){try{startActivity(intent);}catch(RuntimeException e){problem("Setting unavailable on this phone");}}
    void open(String name){dismissMenu();Pane p=panes.get(name);if(p==null){p=new Pane(name);panes.put(name,p);desk.addView(p);p.layout(0);}p.setVisibility(View.VISIBLE);p.bringToFront();}
    class Pane extends LinearLayout {
        final String title;int mode;float x,y,left,top;
        Pane(String n){super(Desktop.this);title=n;setOrientation(1);setClickable(true);setBackground(plate(INK));setElevation(dp(4));setPadding(dp(3),dp(2),dp(3),dp(4));
            LinearLayout bar=row();addView(bar);TextView cap=text(n,16);bar.addView(cap,new LinearLayout.LayoutParams(0,dp(46),1));
            cap.setOnTouchListener((v,e)->{if(e.getAction()==0){bringToFront();x=e.getRawX();y=e.getRawY();left=getX();top=getY();}else if(e.getAction()==MotionEvent.ACTION_MOVE&&mode==0){setX(Math.max(0,Math.min(desk.getWidth()-getWidth(),left+e.getRawX()-x)));setY(Math.max(0,Math.min(desk.getHeight()-getHeight(),top+e.getRawY()-y)));}return true;});
            action(bar,"−",()->setVisibility(View.GONE)).setContentDescription("Minimize "+n);
            action(bar,"□",()->layout(mode==1?0:1)).setContentDescription("Maximize or restore "+n);
            TextView more=text("⋮",24);more.setGravity(Gravity.CENTER);bar.addView(more,dp(44),dp(48));more.setContentDescription("Window options");more.setOnClickListener(v->popup(v,new String[]{"Snap left","Snap right","Restore","Close"},i->{if(i<3)layout(new int[]{2,3,0}[i]);else {setVisibility(View.GONE);tasks.removeView(task);panes.remove(title);desk.removeView(this);}}));
            if(n.equals("MCP tools"))addView(mcpTools(),-1,-1);else if(n.equals("Studio"))addView(studio(),-1,-1);else if(n.equals("Workbench"))addView(workbench(),-1,-1);else{ScrollView scroll=new ScrollView(Desktop.this);LinearLayout list=column();scroll.addView(list);addView(scroll);action(list,"Creative Mode",()->toggleCreative());action(list,"Android screensaver",()->system(new Intent(Settings.ACTION_DREAM_SETTINGS)));action(list,"Default Home app",()->system(new Intent(Settings.ACTION_HOME_SETTINGS)));action(list,"Android settings",()->system(new Intent(Settings.ACTION_SETTINGS)));action(list,"Battery settings",()->system(new Intent(Settings.ACTION_BATTERY_SAVER_SETTINGS)));}
            task=text(n.equals("Control Panel")?"Settings":n,14);task.setPadding(dp(5),0,dp(5),0);task.setGravity(Gravity.CENTER);tasks.addView(task,new LinearLayout.LayoutParams(-2,dp(50)));task.setOnClickListener(v->open(n));
        }
        TextView task;
        void layout(int m){mode=m;int w=desk.getWidth(),h=desk.getHeight();int pw=m==0?Math.min(dp(540),w-dp(16)):m>=2?w/2:w;
            int ph=m==0?Math.min(dp(530),h-dp(24)):h;setLayoutParams(new FrameLayout.LayoutParams(Math.max(1,pw),Math.max(1,ph)));setTranslationX(m==3?w-pw:m==0?(w-pw)/2:0);setTranslationY(m==0?(h-ph)/2:0);}
    }
    protected void onDestroy(){if(sounds!=null)sounds.release();super.onDestroy();}
    public void onBackPressed(){if(creative!=null){toggleCreative();return;}if(menu!=null){dismissMenu();return;}for(int i=desk.getChildCount()-1;i>=0;i--){View v=desk.getChildAt(i);if(v instanceof Pane&&v.isShown()){v.setVisibility(View.GONE);return;}}}
}
