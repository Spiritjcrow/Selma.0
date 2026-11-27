package org.selma.home;

import android.content.*;
import android.graphics.*;
import android.os.SystemClock;
import android.view.View;

class MotionScene extends View {
    final Paint p=new Paint(3);
    final SharedPreferences prefs;
    final boolean dream;
    Bitmap custom;
    float time;long last;
    MotionScene(Context c,boolean saver){super(c);dream=saver;prefs=c.getSharedPreferences("home",0);}
    void oval(Canvas c,float x,float y,float rx,float ry,int color){p.setColor(color);c.drawOval(x-rx,y-ry,x+rx,y+ry,p);}
    void line(Canvas c,float x,float y,float xx,float yy,float width,int color){p.setColor(color);p.setStrokeWidth(width);p.setStrokeCap(Paint.Cap.ROUND);c.drawLine(x,y,xx,yy,p);}
    void box(Canvas c,float x,float y,float w,float h,int color){p.setColor(color);c.drawRoundRect(x,y,x+w,y+h,4,4,p);}
    static float sin(double t){return (float)Math.sin(t);}
    static float cos(double t){return (float)Math.cos(t);}
    protected void onDraw(Canvas c){
        long now=SystemClock.uptimeMillis();float dt=Math.min(60,now-last)/1000f;last=now;
        int speed=prefs.getInt("speed",55);time+=dt*speed/50f;float w=getWidth(),h=getHeight();
        String mode=dream?"toasters":prefs.getString("scene","ship");
        if(mode.equals("custom")&&custom!=null){float k=Math.max(w/custom.getWidth(),h/custom.getHeight());c.save();c.translate((w-custom.getWidth()*k)/2,(h-custom.getHeight()*k)/2);c.scale(k,k);p.setColor(-1);c.drawBitmap(custom,0,0,p);c.restore();return;}
        c.drawColor(0xff100e23);int accent=prefs.getInt("accent",0xffed67ca);
        for(int i=0;i<72;i++)oval(c,((i*523)%1013)/1013f*w,((i*313)%709)/709f*h,1+i%3,1+i%3,i%6==0?accent:0xff9285af);
        if(mode.equals("toasters")){for(int i=0;i<8;i++){float z=.48f+i*.09f;
            float x=w+65-((time*(20+i*2)+i*159)%(w+135));float y=((i*.13f*h+time*(4+i))%(h+90))-35;c.save();c.translate(x,y);c.scale(z*w/390,z*w/390);toaster(c,time*5+i);c.restore();}}
        else{
            for(int i=-5;i<12;i++)line(c,w*.53f,h*.44f,w*i*.25f,h,1.3f,0xff573569);
            for(int i=1;i<=9;i++){float y=h*(.44f+.0069f*i*i);line(c,0,y,w,y,1.5f,0xff634271);}
            float phase=time*.35f, depth=sin(phase),x=w*(.5f+.19f*cos(phase)),y=h*(.55f+depth*.12f);
            float scale=Math.min(w/225,h/220)*(.92f+.13f*depth);float facing=sin(phase)>=0?1:-1;
            float tx=x-67*scale*facing,ty=y+24*scale;
            int count=prefs.getInt("dust",60)*2;
            for(int i=0;i<count;i++){float age=(time*.32f+i*.618034f)%1,shrink=1-age;
                float px=w*((i*173%811)/811f),py=h*(.38f+.6f*(i*97%919)/919f);
                float dx=tx+(px-tx)*shrink+sin(age*13+i)*14*shrink,dy=ty+(py-ty)*shrink+cos(age*9+i)*10*shrink;
                oval(c,dx,dy,1+2*shrink,1+2*shrink,i%3==0?accent:i%3==1?0xff70ffdf:0xffffcd60);}
            c.save();c.translate(x,y);c.scale(facing*scale,scale);crew(c,time*7);c.restore();
        }
        if(isShown()&&getWindowVisibility()==VISIBLE&&speed>0)postInvalidateDelayed(33);
    }
    void toaster(Canvas c,float t){
        for(int side:new int[]{-1,1}){c.save();c.scale(side,1);c.rotate(-18-25*sin(t),17,-4);
            for(int j=0;j<4;j++)oval(c,27+j*2,-8-j*2,12-j,4,0xffddd1fb);c.restore();}
        box(c,-21,-13,42,28,0xff9da9b9);box(c,-18,-14,34,6,0xff414451);
        box(c,-12,-21+3*sin(t),22,12,0xffe5af76);line(c,-17,9,13,9,1,0xffe6f1ff);oval(c,14,1,3,3,0xffec7852);
    }
    void crew(Canvas c,float gait){
        oval(c,0,28,60,6,0xff252235);
        for(int i=0;i<4;i++){float x=-24+i*14;line(c,x,6,x+6*sin(gait+i*2),24,10,0xff805139);}
        oval(c,1,-2,42,24,0xff875231);oval(c,-32,-6,22,24,0xffa4663e);
        for(int i=0;i<70;i++){float a=i*2.4f,r=(i%11)/11f;float x=cos(a)*37*r,y=-2+sin(a)*20*r;line(c,x,y,x-2,y+4,1.5f,0xffb2774b);}
        line(c,-44,-4,-51,13,12,0xffa06642);line(c,-51,13,-66,23,10,0xffad7350);oval(c,-68,24,4,3,0xff513441);
        oval(c,-39,-11,6,5,0xffeed8b3);oval(c,-40,-10,2,3,0xff251926);line(c,-45,-15,-34,-14,3,0xff543226);
        for(int i=0;i<2;i++){int s=i==0?1:-1;float x=i==0?-13:13;
            oval(c,x,-47,6,7,0xffe5b18b);oval(c,x-s*2,-51,6,4,i==0?0xff36232e:0xffae5038);
            line(c,x,-39,x,-27,8,i==0?0xffaabacb:0xff46384e);line(c,x,-27,x+s*8,-23,5,0xff657489);line(c,x+s*8,-23,x+s*7,-16,4,0xff2b2637);}
        for(int i=0;i<2;i++){float x=43+i*15,y=6+i*8;int color=i==0?0xff79cdb0:0xffc5a5dd;
            oval(c,x,y-20,6+i*2,8-i*2,color);line(c,x,y-12,x+2,y,6,0xff686982);
            for(int j=0;j<2;j++){line(c,x+2,y,x+2+sin(gait+i+j*3)*5,y+8,2,color);oval(c,x-3+j*5,y-21,1.4f,2,0xff292334);}}
    }
}
