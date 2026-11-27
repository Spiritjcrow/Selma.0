package org.selma.home;

import java.io.*;
import java.nio.*;
import java.util.*;

/** CPU-only decoder for the bundled, tied-weight TinyStories 260K checkpoint. */
public final class StoryModel {
    static final int D=64, F=172, L=5, H=8, KV=32, S=8, V=512, LIMIT=160;
    final float[] w;
    final String[] pieces=new String[V];
    final float[] score=new float[V];
    final Map<String,Integer> ids=new HashMap<String,Integer>();
    final int att=V*D, q=att+L*D, k=q+L*D*D, v=k+L*D*KV, o=v+L*D*KV,
        ff=o+L*D*D, gate=ff+L*D, down=gate+L*D*F, up=down+L*F*D, end=up+L*D*F;
    static ByteBuffer bytes(InputStream in) throws IOException {
        try { ByteArrayOutputStream b=new ByteArrayOutputStream(); byte[] buf=new byte[8192]; int n;
            while((n=in.read(buf))!=-1)b.write(buf,0,n);
            return ByteBuffer.wrap(b.toByteArray()).order(ByteOrder.LITTLE_ENDIAN);
        } finally {in.close();}
    }
    public StoryModel(InputStream weights,InputStream tokenizer) throws IOException {
        ByteBuffer b=bytes(weights);
        for(int expected:new int[]{D,F,L,H,4,V,512})if(b.getInt()!=expected)throw new IOException("Unsupported model");
        w=new float[b.remaining()/4]; b.asFloatBuffer().get(w);
        if(w.length!=end+D+512*S)throw new IOException("Incomplete model");
        for(float t:w)if(!Float.isFinite(t) || Math.abs(t)>1000)throw new IOException("Invalid model weight");
        b=bytes(tokenizer); b.getInt();
        for(int i=0;i<V;i++){score[i]=b.getFloat(); byte[] data=new byte[b.getInt()]; b.get(data); pieces[i]=new String(data,"UTF-8"); ids.put(pieces[i],i);}
    }
    List<Integer> encode(String text) throws IOException {
        List<Integer> tokens=new ArrayList<Integer>(); tokens.add(1);
        if(!text.isEmpty())tokens.add(ids.get(" "));
        for(int i=0;i<text.length();){int cp=text.codePointAt(i);String s=new String(Character.toChars(cp));i+=s.length();
            Integer id=ids.get(s); if(id!=null)tokens.add(id);else for(byte b:s.getBytes("UTF-8"))tokens.add(3+(b&255));}
        for(;;){float best=-Float.MAX_VALUE;int at=-1,merged=-1;
            for(int i=1;i+1<tokens.size();i++){Integer id=ids.get(pieces[tokens.get(i)]+pieces[tokens.get(i+1)]);
                if(id!=null && score[id]>best){best=score[id];at=i;merged=id;}}
            if(at<0)return tokens; tokens.set(at,merged);tokens.remove(at+1);}
    }
    void norm(float[] out,float[] x,int offset){float sum=0;for(float t:x)sum+=t*t;
        float scale=(float)(1/Math.sqrt(sum/x.length+1e-5));for(int i=0;i<x.length;i++)out[i]=w[offset+i]*x[i]*scale;}
    void mat(float[] out,float[] x,int offset){for(int i=0;i<out.length;i++){float sum=0;for(float val:x)sum+=w[offset++]*val;out[i]=sum;}}
    void rotate(float[] a,int pos){for(int i=0;i<a.length;i+=2){double angle=pos/Math.pow(10000,(i%S)/(double)S);
        float c=(float)Math.cos(angle),s=(float)Math.sin(angle),x=a[i],y=a[i+1];a[i]=x*c-y*s;a[i+1]=x*s+y*c;}}
    public String complete(String prompt,int count) throws IOException {
        if(prompt.length()>256 || count<1 || count>64)throw new IOException("Use a shorter prompt or output");
        List<Integer> tokens=encode(prompt);if(tokens.size()+count>LIMIT)throw new IOException("Use a shorter prompt");
        float[][] keys=new float[L][LIMIT*KV],values=new float[L][LIMIT*KV];
        float[] x=new float[D],a=new float[D],query=new float[D],key=new float[KV],value=new float[KV],
            context=new float[D],hidden=new float[F],other=new float[F],prob=new float[LIMIT],logits=new float[V];
        StringBuilder out=new StringBuilder();int token=1;
        for(int pos=0;pos<tokens.size()+count-1;pos++){
            if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();
            if(pos<tokens.size())token=tokens.get(pos);
            System.arraycopy(w,token*D,x,0,D);
            for(int layer=0;layer<L;layer++){
                norm(a,x,att+layer*D);mat(query,a,q+layer*D*D);mat(key,a,k+layer*D*KV);mat(value,a,v+layer*D*KV);
                rotate(query,pos);rotate(key,pos);System.arraycopy(key,0,keys[layer],pos*KV,KV);System.arraycopy(value,0,values[layer],pos*KV,KV);
                Arrays.fill(context,0);
                for(int h=0;h<H;h++){int base=h/2*S;float max=-Float.MAX_VALUE;
                    for(int t=0;t<=pos;t++){float z=0;for(int i=0;i<S;i++)z+=query[h*S+i]*keys[layer][t*KV+base+i];
                        prob[t]=(float)(z/Math.sqrt(S));max=Math.max(max,prob[t]);}
                    float total=0;for(int t=0;t<=pos;t++){prob[t]=(float)Math.exp(prob[t]-max);total+=prob[t];}
                    for(int t=0;t<=pos;t++)for(int i=0;i<S;i++)context[h*S+i]+=prob[t]/total*values[layer][t*KV+base+i];}
                mat(a,context,o+layer*D*D);for(int i=0;i<D;i++)x[i]+=a[i];
                norm(a,x,ff+layer*D);mat(hidden,a,gate+layer*D*F);mat(other,a,up+layer*D*F);
                for(int i=0;i<F;i++)hidden[i]=(float)(hidden[i]/(1+Math.exp(-hidden[i]))*other[i]);
                mat(a,hidden,down+layer*F*D);for(int i=0;i<D;i++)x[i]+=a[i];
            }
            if(pos+1<tokens.size())continue;
            norm(a,x,end);mat(logits,a,0);token=0;for(int i=1;i<V;i++)if(logits[i]>logits[token])token=i;
            if(token<=2)break;
            if(token>=3 && token<259)out.append((char)(token-3));else out.append(pieces[token]);
        }
        return out.toString();
    }
}
