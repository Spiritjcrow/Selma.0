package org.selma.home;
import android.graphics.*;
final class MeatMorph {
    static final int N=96;
    final float[][] xs=new float[4][N],ys=new float[4][N];
    final Path path=new Path();final Paint pen=new Paint(3);
    MeatMorph(){
        for(int j=0;j<4;j++)for(int i=0;i<N;i++){double a=i*2*Math.PI/N;double x=Math.cos(a),y=Math.sin(a);
            double radius=1+.04*Math.cos(7*a)+.025*Math.sin(11*a);
            xs[j][i]=(float)(j==0?24*x*radius:j==1?40*Math.copySign(Math.pow(Math.abs(x),.72),x):j==2?34*x:16*x);
            ys[j][i]=(float)(j==0?20*y*radius:j==1?11*Math.copySign(Math.pow(Math.abs(y),.75),y)-4*x*x:j==2?Math.min(7,26*y)+3:24*y);
        }
    }
    float mix(float a,float b,float t){return a+(b-a)*t;}
    void draw(Canvas c,long ms){float beat=ms/1450f;int a=((int)beat)%4,b=(a+1)%4;float f=beat-(int)beat;
        float u=Math.max(0,Math.min(1,(f-.22f)/.72f));float t=u*u*(3-2*u)+.13f*MotionScene.sin(Math.PI*2*u)*u*(1-u);
        float recoil=MotionScene.sin(Math.PI*2*u)*MotionScene.sin(Math.PI*u)*.1f;
        c.save();c.scale(1+recoil,1-recoil);
        path.rewind();for(int i=0;i<N;i++){float x=mix(xs[a][i],xs[b][i],t),y=mix(ys[a][i],ys[b][i],t);if(i==0)path.moveTo(x,y);else path.lineTo(x,y);}path.close();
        pen.setColor(0xffa8503b);c.drawPath(path,pen);c.save();c.clipPath(path);pen.setColor(0xff8d422f);
        for(int i=0;i<37;i++)c.drawCircle((i*17%73)-36,(i*23%47)-23,1+i%2,pen);c.restore();
        float lin=(a==3?1-t:0)+(b==3?t:0);float ig=(a==2?1-t:0)+(b==2?t:0);
        if(ig>0){pen.setColor(0xff6a3027);pen.setAlpha((int)(ig*200));c.save();c.clipPath(path);for(int i=-2;i<=1;i++){c.drawRect(-34,i*8,34,i*8+1,pen);for(int j=-2;j<3;j++)c.drawRect(j*13+(i%2)*6,i*8,j*13+(i%2)*6+1,i*8+8,pen);}c.restore();}
        if(lin>0){c.save();c.translate(0,-15*lin);c.scale(lin,lin);pen.setColor(0xff251e29);c.drawRect(-15,-10,15,-7,pen);c.drawRect(-10,-29,10,-9,pen);c.restore();
            c.save();c.translate(14,8);c.scale(lin,lin);c.rotate(-16);pen.setColor(0xffcbcde3);path.rewind();path.moveTo(3,0);path.quadTo(25,-6,38,-21);path.quadTo(24,-1,4,3);path.close();c.drawPath(path,pen);pen.setColor(0xffbc8d47);c.drawRect(-2,-2,4,4,pen);c.restore();}
        float eyeY=mix(a==1?-3:-6,b==1?-3:-6,t);
        for(int i:new int[]{-6,5}){pen.setColor(0xfff9edce);c.drawOval(i-3,eyeY-3,i+3,eyeY+3,pen);pen.setColor(0xff201922);c.drawCircle(i+1,eyeY,1.5f,pen);}
        pen.setColor(0xff442326);c.drawOval(-6,eyeY+6,6,eyeY+10,pen);pen.setColor(0xffe7ceaa);c.drawRect(-1,eyeY+6,2,eyeY+9,pen);c.restore();
    }
}
