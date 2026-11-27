package org.selma.home;

import android.app.job.*;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.provider.DocumentsContract.Document;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class ReviewJob extends JobService {
    static final int MANUAL=6201, DAILY=6202;
    final Set<JobParameters> canceled=Collections.synchronizedSet(new HashSet<>());
    public boolean onStartJob(JobParameters p){
        new Thread(()->{synchronized(ReviewJob.class){if(canceled.remove(p))return;
            SharedPreferences prefs=getSharedPreferences("workbench",0);
            prefs.edit().putString("status","Running").commit();
            try{String report=scan(prefs,p);if(canceled.remove(p))return;
                AtomicFile f=new AtomicFile(new File(getFilesDir(),"review.txt"));FileOutputStream out=f.startWrite();
                try{out.write(report.getBytes(StandardCharsets.UTF_8));f.finishWrite(out);}catch(IOException e){f.failWrite(out);throw e;}
                prefs.edit().putString("status","Completed · "+new Date()).commit();
            }catch(Exception e){prefs.edit().putString("status","Stopped · "+e.getMessage()).commit();}}
            if(!canceled.remove(p))jobFinished(p,false);},"selma-review").start();return true;}
    public boolean onStopJob(JobParameters p){canceled.add(p);getSharedPreferences("workbench",0).edit().putString("status","Interrupted by Android").apply();return true;}
    String scan(SharedPreferences prefs,JobParameters p)throws IOException{
        String tree=prefs.getString("tree","");if(tree.isEmpty())throw new IOException("Choose a project folder");
        Uri root=Uri.parse(tree);ArrayDeque<String[]> dirs=new ArrayDeque<>();dirs.add(new String[]{DocumentsContract.getTreeDocumentId(root),""});
        String focus=prefs.getString("focus","").trim().toLowerCase(Locale.ROOT);
        int files=0, sources=0, hits=0, visited=0;long readBytes=0;
        StringBuilder manifests=new StringBuilder(),matches=new StringBuilder();boolean limited=false;
        Set<String> skip=new HashSet<>(Arrays.asList(".git","node_modules",".gradle","build","dist",".next",".venv","__pycache__"));
        Set<String> seen=new HashSet<>();
        outer:while(!dirs.isEmpty()&&!canceled.contains(p)){String[] dir=dirs.removeFirst();if(!seen.add(dir[0]))continue;
            Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(root,dir[0]);
            try(Cursor c=getContentResolver().query(children,new String[]{Document.COLUMN_DOCUMENT_ID,Document.COLUMN_DISPLAY_NAME,Document.COLUMN_MIME_TYPE},null,null,null)){
                if(c==null)throw new IOException("Folder unavailable");
                while(c.moveToNext()&&!canceled.contains(p)){if(++visited>5000){limited=true;break outer;}String id=c.getString(0),name=c.getString(1);if(name==null)continue;
                    String path=dir[1]+name;
                    if(Document.MIME_TYPE_DIR.equals(c.getString(2))){if(!skip.contains(name))dirs.add(new String[]{id,path+"/"});continue;}
                    files++;if(name.matches("package\\.json|pyproject\\.toml|requirements.*\\.txt|build\\.gradle(\\.kts)?|Cargo\\.toml|go\\.mod|Dockerfile|.*\\.csproj")||path.startsWith(".github/workflows/"))manifests.append(path).append('\n');
                    if(!name.matches(".*\\.(py|tsx?|jsx?|java|kt|rs|go|cpp|cs|ya?ml|sh)$"))continue;
                    if(readBytes>=8*1024*1024){limited=true;continue;}sources++;
                    try(InputStream in=getContentResolver().openInputStream(DocumentsContract.buildDocumentUriUsingTree(root,id))){
                        if(in==null)throw new IOException("Unreadable: "+path);
                        ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] buf=new byte[4096];int n;
                        while(bytes.size()<65536&&(n=in.read(buf))>0)bytes.write(buf,0,n);
                        if(bytes.size()==65536)limited=true;readBytes+=bytes.size();
                        int ln=0;for(String line:new String(bytes.toByteArray(),StandardCharsets.UTF_8).split("\n")){ln++;
                            String l=line.toLowerCase(Locale.ROOT);if(l.contains("todo")||l.contains("fixme")||(!focus.isEmpty()&&l.contains(focus))){
                                if(++hits<=150)matches.append(path).append(':').append(ln).append("  ").append(line.substring(0,Math.min(150,line.length())).trim()).append('\n');}}
                    }
                }
            }
        }
        return "Project review · "+new Date()+"\n"+files+" files inventoried · "+sources+" source files inspected\n"+(limited?"Scan limits reached. Partial coverage.\n":"")+"Focus keyword: "+focus+"\n\nBuild and workflow files\n"+(manifests.length()==0?"None found\n":manifests)+"\nSource findings ("+hits+", first 150 shown)\n"+(hits==0?"None found\n":matches);
    }
}
