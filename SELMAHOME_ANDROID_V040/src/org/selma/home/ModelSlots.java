package org.selma.home;

import java.io.*;
import java.util.UUID;

/** Copy into an unpublished file; the caller commits the selected name only after a smoke test. */
final class ModelSlots {
    static File stage(File directory,InputStream source)throws IOException{
        File file=new File(directory,"model-"+UUID.randomUUID()+".bin");boolean ok=false;
        try(InputStream in=source;FileOutputStream out=new FileOutputStream(file)){
            byte[] b=new byte[8192];int n,total=0;
            while((n=in.read(b))!=-1){total+=n;if(total>1056540)throw new IOException("Wrong checkpoint size");out.write(b,0,n);}
            if(total!=1056540)throw new IOException("Incomplete checkpoint");out.getFD().sync();ok=true;
        }finally{if(!ok)file.delete();}return file;
    }
}
