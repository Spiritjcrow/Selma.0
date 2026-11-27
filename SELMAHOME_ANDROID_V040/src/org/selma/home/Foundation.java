package org.selma.home;

import android.content.Context;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.provider.DocumentsContract.Document;
import java.io.*;
import java.util.*;

final class Foundation {
    static Uri create(Context c, Uri tree)throws IOException {
        Uri parent=DocumentsContract.buildDocumentUriUsingTree(tree,DocumentsContract.getTreeDocumentId(tree));
        Uri root=DocumentsContract.createDocument(c.getContentResolver(),parent,Document.MIME_TYPE_DIR,"selma-project-"+UUID.randomUUID().toString().substring(0,8));
        if(root==null)throw new IOException("Cannot create project folder");
        try{copy(c,root,"foundation");return root;}catch(IOException|RuntimeException e){throw new IOException("Incomplete new project at "+root.getLastPathSegment()+": "+e.getMessage(),e);}
    }
    static void copy(Context c,Uri parent,String path)throws IOException{
        for(String name:c.getAssets().list(path)){
            String child=path+"/"+name;boolean folder=c.getAssets().list(child).length>0;
            Uri out=DocumentsContract.createDocument(c.getContentResolver(),parent,folder?Document.MIME_TYPE_DIR:"application/octet-stream",name);
            if(out==null)throw new IOException("Cannot create "+name);
            if(folder){copy(c,out,child);continue;}
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(InputStream in=c.getAssets().open(child)){byte[] buf=new byte[4096];int n;while((n=in.read(buf))!=-1)bytes.write(buf,0,n);}
            try(OutputStream stream=c.getContentResolver().openOutputStream(out,"w")){if(stream==null)throw new IOException(name);bytes.writeTo(stream);}
            try(InputStream in=c.getContentResolver().openInputStream(out)){if(in==null)throw new IOException(name);for(byte b:bytes.toByteArray())if(in.read()!=(b&255))throw new IOException("Verification failed: "+name);if(in.read()!=-1)throw new IOException(name);}
        }
    }
}
