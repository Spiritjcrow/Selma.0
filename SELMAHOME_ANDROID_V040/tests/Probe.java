package org.selma.home;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import org.json.*;
public class Probe {
    static void check(boolean b){if(!b)throw new AssertionError();}
    static String call(ToolServer s,String body,boolean auth,int expected)throws Exception{
        HttpURLConnection c=(HttpURLConnection)new URL("http://127.0.0.1:"+s.server.getLocalPort()+"/mcp").openConnection();
        c.setRequestMethod("POST");c.setDoOutput(true);if(auth)c.setRequestProperty("Authorization","Bearer "+s.secret);
        try(OutputStream out=c.getOutputStream()){out.write(body.getBytes(StandardCharsets.UTF_8));}
        check(c.getResponseCode()==expected);if(expected!=200){c.disconnect();return "";}
        try(BufferedReader r=new BufferedReader(new InputStreamReader(c.getInputStream(),"UTF-8"))){return r.readLine();}finally{c.disconnect();}
    }
    public static void main(String[] args)throws Exception{
        StoryModel model=new StoryModel(new FileInputStream(args[0]),new FileInputStream(args[1]));
        String prompt="Once upon a time";String story=model.complete(prompt,36);check(!story.trim().isEmpty());check(model.complete(prompt,36).equals(story));
        System.out.println(prompt+story);
        try{ModelSlots.stage(new File(args[2]),new ByteArrayInputStream(new byte[8]));throw new AssertionError();}catch(IOException expected){}
        File f=ModelSlots.stage(new File(args[2]),new FileInputStream(args[0]));check(f.length()==1056540);check(f.delete());
        try(ToolServer s=new ToolServer(p->model.complete(p,36),name->name)){s.start();
            String base="{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"";
            HttpURLConnection missing=(HttpURLConnection)new URL("http://127.0.0.1:"+s.server.getLocalPort()+"/missing").openConnection();
            missing.setRequestProperty("Authorization","Bearer "+s.secret);
            java.util.ArrayList<String> errors=new java.util.ArrayList<>();s.errors=errors::add;
            check(missing.getResponseCode()==404);missing.disconnect();
            check(errors.contains("404 Not Found"));
            call(s,base+"ping\"}",false,401);
            check(call(s,base+"initialize\"}",true,200).contains("2025-06-18"));
            call(s,"{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}",true,202);
            check(call(s,base+"tools/list\"}",true,200).contains("story_complete"));
            for(String name:ToolServer.WORK){
                String request=base+"tools/call\",\"params\":{\"name\":\""+name+"\"}}";
                call(s,request,false,401);
                check(new JSONObject(call(s,request,true,200)).getJSONObject("result").getJSONArray("content").getJSONObject(0).getString("text").equals(name));
            }
            String result=call(s,base+"tools/call\",\"params\":{\"name\":\"story_complete\",\"arguments\":{\"prompt\":\"Once upon a time\"}}}",true,200);
            check(new JSONObject(result).getJSONObject("result").getJSONArray("content").getJSONObject(0).getString("text").equals(story));
            check(call(s,base+"unknown\"}",true,200).contains("-32601"));
        }System.out.println("PASS offline generation, repeatability, checkpoint staging, MCP authorization, initialization, discovery and inference");}
}
