package org.selma.home;

import android.content.Context;
import android.graphics.*;
import android.os.SystemClock;
import android.view.View;
import java.util.*;

class TapEffects extends View {
    final Paint paint=new Paint(3);
    final ArrayList<Particle> items=new ArrayList<>();
    final Random random=new Random();
    final MeatMorph morph=new MeatMorph();int busy;long since;
    void busy(boolean on){if(on){if(busy++==0)since=SystemClock.uptimeMillis();}else busy=Math.max(0,busy-1);invalidate();}
    long errorTime;String error="";
    static class Particle {float x,y,vx,vy;int kind;long born;}
    TapEffects(Context c){super(c);setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);}
    void burst(float x,float y){for(int i=0;i<9;i++){Particle p=new Particle();p.x=x;p.y=y;p.vx=random.nextFloat()*2-1;p.vy=-.2f-random.nextFloat();p.kind=random.nextInt(3);p.born=SystemClock.uptimeMillis();if(items.size()>=90)items.remove(0);items.add(p);}invalidate();}
    void error(String message){error=message==null?"Unknown error":message;errorTime=SystemClock.uptimeMillis();invalidate();}
    void oval(Canvas c,float x,float y,float rx,float ry,int color){paint.setColor(color);c.drawOval(x-rx,y-ry,x+rx,y+ry,paint);}
    void glyph(Canvas c,int type){if(type==0){for(int i=-2;i<=2;i++){c.save();c.rotate(i*24);oval(c,0,-3,1.4f,4,0xff77dc82);c.restore();}}
        else if(type==1){oval(c,0,0,4,3,0xff41344f);oval(c,3,-2,2.6f,2.7f,0xff46354c);oval(c,5.7f,-2,2,1,0xffeba95a);oval(c,-1,-1,2,1,0xffa5a3d3);}
        else{oval(c,-4,0,2,2.5f,0xffc08c61);oval(c,4,0,2,2.5f,0xffc08c61);oval(c,0,-.5f,4,4,0xff956545);oval(c,0,1,2.8f,2,0xffedc298);}}
    protected void onDraw(Canvas c){long now=SystemClock.uptimeMillis();float d=getResources().getDisplayMetrics().density;
        for(Iterator<Particle> it=items.iterator();it.hasNext();){Particle p=it.next();float t=(now-p.born)/920f;if(t>=1){it.remove();continue;}
            c.save();c.translate(p.x+d*p.vx*(92*t),p.y+d*(p.vy*98*t+78*t*t-4*Math.abs(MotionScene.sin(18*t))));c.scale(d*(1-.5f*t),d*(1-.5f*t));c.rotate(p.kind==0?t*175:p.vx*12);glyph(c,p.kind);c.restore();}
        boolean show=errorTime>0&&now-errorTime<3200;
        if(show&&now-errorTime<2000){float u=(now-errorTime)/2000f;float scale=Math.min(getWidth()/126f,getHeight()/130f)*(.78f+.42f*u);int alpha=(int)(140*(1-u)*Math.min(1,u*16));
            c.save();c.translate(getWidth()*.5f,getHeight()*.52f);c.scale(scale,scale);
            c.saveLayerAlpha(-83,-76,83,76,alpha);oval(c,0,-4,34,30,0xffb94b4d);
            for(int i=0;i<6;i++){float x=-27+i*10;paint.setColor(0xffb94b4d);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(6);Path leg=new Path();leg.moveTo(x,12);leg.cubicTo(x-14,46,x+20,54,x+13,30);c.drawPath(leg,paint);paint.setStyle(Paint.Style.FILL);}
            oval(c,-5,-32,26,15,0xffefe4bd);oval(c,-24,-24,23,5,0xff4c6a62);
            for(int x:new int[]{-14,6}){oval(c,x,-9,7,9,0xfff5dfb5);oval(c,x-2,-8,2,4,0xff29232c);}oval(c,-3,8,6,8,0xff362330);
            c.restore();c.restore();}
        if(show){float width=getWidth()/d;c.save();c.scale(d,d);c.translate(width/2,70);paint.setColor(0xf3261c31);c.drawRoundRect(-Math.min(width/2-6,175),-36,Math.min(width/2-6,175),45,10,10,paint);
            float squeeze=Math.abs(MotionScene.sin((now-errorTime)*.004));c.save();c.scale(1-.38f*squeeze,1+.2f*squeeze);
            oval(c,-9,0,9,12,0xffd8aa86);oval(c,-15,-13,3,9,0xffe5b495);oval(c,-6,-14,3,10,0xffddb18e);
            oval(c,13,0,14,14,0xffb9513e);oval(c,14,4,10,7,0xffe7cf9d);oval(c,16,-1,4,3,0xff3e8fb0);
            for(int i:new int[]{-12,-7,9,17})oval(c,i,-5,1.4f,2,0xff242032);c.restore();
            for(int side:new int[]{-1,1}){c.save();c.scale(side,1);c.translate(40-7*squeeze,0);c.scale(2,2);glyph(c,1);oval(c,-4,2,4,2,0xff996fb1);oval(c,-7,0,3,4,0xffb380b7);c.restore();}
            paint.setTextSize(12);paint.setTextAlign(Paint.Align.CENTER);paint.setColor(-1);c.drawText(android.text.TextUtils.ellipsize(error,new android.text.TextPaint(paint),Math.min(width-36,326),android.text.TextUtils.TruncateAt.END).toString(),0,34,paint);c.restore();}
        if(busy>0){c.save();c.translate(getWidth()/2f,getHeight()*.28f);c.scale(d*1.25f,d*1.25f);morph.draw(c,now-since);c.restore();}
        if(show||busy>0||!items.isEmpty())postInvalidateDelayed(25);}
}
