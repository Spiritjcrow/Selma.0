package org.selma.home;

import android.app.*;
import android.os.*;
import android.content.*;
import android.content.pm.*;
import android.view.*;
import android.graphics.Color;
import android.widget.*;
import java.util.*;
import java.io.*;
import java.util.concurrent.*;

public class Home extends Activity {
    LinearLayout body; EditText prompt; TextView result; Button generate,bridge;
    final ExecutorService worker=Executors.newSingleThreadExecutor();
    StoryModel model; ToolServer server; SharedPreferences prefs;
    int dp(int n){return (int)(getResources().getDisplayMetrics().density*n+.5f);}
    TextView label(String s,int size){TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setPadding(0,dp(8),0,dp(4));body.addView(v);return v;}
    Button button(String text,Runnable action){Button b=new Button(this);b.setAllCaps(false);b.setText(text);body.addView(b);b.setOnClickListener(v->action.run());return b;}
    public void onCreate(Bundle state){super.onCreate(state);prefs=getSharedPreferences("home",MODE_PRIVATE);}
    View studio(){ScrollView scroll=new ScrollView(this);body=new LinearLayout(this);body.setOrientation(1);body.setPadding(dp(16),dp(8),dp(16),dp(16));scroll.addView(body);
        label("Offline story completion",20);prompt=new EditText(this);prompt.setHint("Start a short English story");prompt.setSingleLine(false);prompt.setMaxLines(4);
        prompt.setText(prefs.getString("prompt","Once upon a time"));body.addView(prompt);
        generate=button("Continue story",()->infer());result=label(prefs.getString("last",""),17);result.setTextIsSelectable(true);
        label("Local tools",20);bridge=button(server==null?"Start MCP":"Stop MCP",()->switchServer());
        button("Import compatible model",()->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");startActivityForResult(i,7);});
        button("Restore previous model",()->runTask(()->{try{rollback();notice("Previous model restored");}catch(Exception e){problem(e.getMessage());}}));return scroll;}
    void runTask(Runnable r){busy(true);worker.execute(()->{try{r.run();}finally{runOnUiThread(()->busy(false));}});}
    synchronized String complete(String input)throws Exception {if(model==null)model=loadModel(prefs.getString("active",""));return model.complete(input,36);}
    StoryModel loadModel(String name)throws IOException{
        InputStream in=name.isEmpty()?getAssets().open("model.bin"):new FileInputStream(new File(getFilesDir(),name));
        return new StoryModel(in,getAssets().open("tok.bin"));
    }
    void busy(boolean value){}
    void problem(String s){notice(s);}
    void notice(String s){runOnUiThread(()->{if(!isDestroyed())Toast.makeText(this,s,Toast.LENGTH_LONG).show();});}
    protected void onActivityResult(int code,int status,Intent data){super.onActivityResult(code,status,data);
        if(code!=7||status!=RESULT_OK||data==null||data.getData()==null)return;
        runTask(()->{try{installModel(getContentResolver().openInputStream(data.getData()));notice("Model activated");}
            catch(Exception e){problem("Import failed: "+e.getMessage());}});}
    synchronized void installModel(InputStream in)throws Exception{
        if(in==null)throw new IOException("Cannot open file");
        File next=ModelSlots.stage(getFilesDir(),in);boolean committed=false;
        try{StoryModel candidate=loadModel(next.getName());
            if(candidate.complete("Once upon a time",8).trim().isEmpty())throw new IOException("Smoke test returned empty text");
            String old=prefs.getString("active",""),stale=prefs.getString("previous","");
            if(!prefs.edit().putString("active",next.getName()).putString("previous",old).commit())throw new IOException("Cannot save selection");
            committed=true;model=candidate;if(!stale.isEmpty()&&!stale.equals(old))new File(getFilesDir(),stale).delete();
        }finally{if(!committed)next.delete();}}
    synchronized void rollback()throws Exception{
        if(!prefs.contains("previous"))throw new IOException("No model upgrade to reverse");
        String previous=prefs.getString("previous",""),active=prefs.getString("active","");
        StoryModel candidate=loadModel(previous);
        if(!prefs.edit().putString("active",previous).remove("previous").commit())throw new IOException("Cannot restore selection");
        model=candidate;if(!active.isEmpty()&&!active.equals(previous))new File(getFilesDir(),active).delete();}
    void infer(){final String input=prompt.getText().toString();generate.setEnabled(false);result.setText("Generating on this device…");
        runTask(()->{try{String text=input+complete(input);prefs.edit().putString("prompt",input).putString("last",text).apply();
                runOnUiThread(()->finishText(text));}catch(Exception e){runOnUiThread(()->{problem(e.getMessage());finishText(e.getMessage());});}});}
    void finishText(String s){if(!isDestroyed()){result.setText(s);generate.setEnabled(true);}}
    String workbenchTool(String name)throws IOException{
        SharedPreferences jobs=getSharedPreferences("workbench",MODE_PRIVATE);
        if(name.equals("review_status")){
            android.app.job.JobScheduler scheduler=getSystemService(android.app.job.JobScheduler.class);
            return "Manual review scheduled: "+(scheduler.getPendingJob(ReviewJob.MANUAL)!=null)+"\nDaily review scheduled: "+(scheduler.getPendingJob(ReviewJob.DAILY)!=null)+"\nLast recorded status: "+jobs.getString("status","No runs yet");
        }
        if(name.equals("review_report")){
            android.util.AtomicFile file=new android.util.AtomicFile(new File(getFilesDir(),"review.txt"));
            try{return new String(file.readFully(),java.nio.charset.StandardCharsets.UTF_8);}
            catch(FileNotFoundException e){throw new IOException("No completed project review yet");}
        }
        if(jobs.getString("tree","").isEmpty())throw new IOException("Choose a project folder in Workbench first");
        android.app.job.JobScheduler js=getSystemService(android.app.job.JobScheduler.class);
        if(js.getPendingJob(ReviewJob.MANUAL)!=null)return "A manual review is already scheduled";
        android.app.job.JobInfo job=new android.app.job.JobInfo.Builder(ReviewJob.MANUAL,new ComponentName(this,ReviewJob.class)).setOverrideDeadline(0).build();
        if(js.schedule(job)!=android.app.job.JobScheduler.RESULT_SUCCESS)throw new IOException("Android declined scheduling");
        return "Review submitted to Android";
    }
    void switchServer(){if(server!=null){stopServer();return;}try{server=new ToolServer(this::complete,this::workbenchTool);server.errors=this::problem;server.start();serverChanged();showConnection();
        }catch(Exception e){stopServer();problem("MCP unavailable");}}
    void showConnection(){if(server==null)return;
        TextView info=new TextView(this);info.setPadding(dp(16),dp(16),dp(16),dp(16));info.setTextIsSelectable(true);
        info.setText("http://127.0.0.1:"+server.server.getLocalPort()+"/mcp\nAuthorization: Bearer "+server.secret+"\n\nConnected clients can queue a review and read its source findings while Selma Home is visible.");
        new AlertDialog.Builder(this).setTitle("MCP connection").setView(info).setPositiveButton("Done",null).show();
    }
    void serverChanged(){if(bridge!=null)bridge.setText(server==null?"Start MCP":"Stop MCP");}
    void stopServer(){if(server!=null)try{server.close();}catch(Exception ignored){}server=null;serverChanged();}
    protected void onStop(){stopServer();super.onStop();}
    protected void onDestroy(){worker.shutdownNow();super.onDestroy();}
}
