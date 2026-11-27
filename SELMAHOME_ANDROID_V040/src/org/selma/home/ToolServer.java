package org.selma.home;

import org.json.*;
import java.io.*;
import java.net.*;
import java.security.*;
import java.util.*;

/** Foreground-only stateless MCP Streamable HTTP endpoint. */
final class ToolServer implements Closeable {
    interface Tools {String complete(String prompt) throws Exception;}
    java.util.function.Consumer<String> errors=s->{};
    final Tools tools;
    interface Workbench {String call(String name)throws Exception;}
    final Workbench workbench;
    static final String[] WORK={"review_status","review_report","review_run"};
    static final String[] HELP={"Get the current Workbench review status.","Read the last completed project review, including source findings.","Queue a review of the folder selected in Workbench."};
    final String secret;
    final ServerSocket server;
    volatile Socket active;
    ToolServer(Tools tools,Workbench workbench) throws IOException {
        this.tools=tools;this.workbench=workbench;
        byte[] key=new byte[24];new SecureRandom().nextBytes(key);
        StringBuilder s=new StringBuilder();for(byte b:key)s.append(String.format(Locale.ROOT,"%02x",b & 255));secret=s.toString();
        server=new ServerSocket(0,4,InetAddress.getByName("127.0.0.1"));
    }
    void start(){new Thread(()->{while(!server.isClosed()){try(Socket c=server.accept()){
        active=c;if(server.isClosed())break;c.setSoTimeout(2500);handle(c);
    }catch(Exception ignored){}finally{active=null;}}},"Selma-MCP").start();}
    public void close() throws IOException {server.close();Socket c=active;if(c!=null)c.close();}
    static JSONObject obj(Object... pairs)throws JSONException {JSONObject j=new JSONObject();for(int i=0;i<pairs.length;i+=2)j.put((String)pairs[i],pairs[i+1]);return j;}
    static String line(InputStream in)throws IOException {ByteArrayOutputStream b=new ByteArrayOutputStream();
        for(int i=0;i<4096;i++){int ch=in.read();if(ch<0)throw new EOFException();if(ch==10)return b.toString("US-ASCII").trim();b.write(ch);}throw new IOException("Header limit");}
    void reply(OutputStream out,String status,String body)throws IOException {if(status.startsWith("4")||status.startsWith("5"))errors.accept(status);byte[] bytes=body.getBytes("UTF-8");
        out.write(("HTTP/1.1 "+status+"\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: "+bytes.length+"\r\n\r\n").getBytes("US-ASCII"));out.write(bytes);out.flush();}
    void handle(Socket c)throws Exception {
        InputStream in=new BufferedInputStream(c.getInputStream());OutputStream out=c.getOutputStream();
        String request=line(in);Map<String,String> headers=new HashMap<>();
        for(int i=0;;i++){String h=line(in);if(h.isEmpty())break;if(i>=32)return;int colon=h.indexOf(':');if(colon<=0)return;
            String name=h.substring(0,colon).toLowerCase(Locale.ROOT);if(headers.put(name,h.substring(colon+1).trim())!=null)return;}
        if(headers.containsKey("origin") || !("127.0.0.1:"+server.getLocalPort()).equals(headers.get("host"))){reply(out,"403 Forbidden","");return;}
        if(!("Bearer "+secret).equals(headers.get("authorization"))){reply(out,"401 Unauthorized","");return;}
        String[] parts=request.split(" ");if(parts.length==3&&!parts[1].equals("/mcp")){reply(out,"404 Not Found","");return;}
        if(!request.equals("POST /mcp HTTP/1.1")){reply(out,"405 Method Not Allowed","");return;}
        int size;try{size=Integer.parseInt(headers.get("content-length"));}catch(Exception e){size=-1;}
        if(size<1||size>16384||headers.containsKey("transfer-encoding")){reply(out,"400 Bad Request","");return;}
        byte[] raw=new byte[size];new DataInputStream(in).readFully(raw);
        JSONObject req;try{req=new JSONObject(new String(raw,"UTF-8"));}catch(JSONException e){reply(out,"400 Bad Request","");return;}
        if(!"2.0".equals(req.optString("jsonrpc"))||!req.has("method")){reply(out,"400 Bad Request","");return;}
        if(!req.has("id")){reply(out,"202 Accepted","");return;}
        JSONObject response=obj("jsonrpc","2.0","id",req.get("id"));Object result=null;
        switch(req.optString("method")){
        case "initialize":result=obj("protocolVersion","2025-06-18","capabilities",obj("tools",obj()),"serverInfo",obj("name","selma-home","version","0.4.0"));break;
        case "ping":result=obj();break;
        case "tools/list":
            JSONArray list=new JSONArray().put(obj("name","story_complete","description","Continue a short story offline.","inputSchema",obj("type","object","properties",obj("prompt",obj("type","string","maxLength",256)),"required",new JSONArray().put("prompt"))));
            for(int i=0;i<WORK.length;i++)list.put(obj("name",WORK[i],"description",HELP[i],"inputSchema",obj("type","object","properties",obj(),"additionalProperties",false)));
            result=obj("tools",list);break;
        case "tools/call":
            try{
                JSONObject params=req.getJSONObject("params");String name=params.getString("name");
                JSONObject args=params.has("arguments")?params.getJSONObject("arguments"):obj();
                String text;
                if(name.equals("story_complete")){
                    Object prompt=args.get("prompt");if(!(prompt instanceof String)||((String)prompt).length()>256)throw new JSONException("Expected up to 256 characters");
                    text=tools.complete((String)prompt);
                }else{
                    if(!Arrays.asList(WORK).contains(name))throw new JSONException("Unknown tool");
                    if(args.length()!=0)throw new JSONException("This tool takes no arguments");
                    text=workbench.call(name);
                }
                result=obj("content",new JSONArray().put(obj("type","text","text",text)));
            }catch(JSONException e){response.put("error",obj("code",-32602,"message",e.getMessage()));}
            catch(Exception e){result=obj("isError",true,"content",new JSONArray().put(obj("type","text","text",e.getMessage()==null?"Tool failed":e.getMessage())));}
            break;
        default:response.put("error",obj("code",-32601,"message","Method not found"));}
        if(result!=null)response.put("result",result);if(response.has("error"))errors.accept(response.getJSONObject("error").optString("message"));else if(result instanceof JSONObject&&((JSONObject)result).optBoolean("isError"))errors.accept("MCP tool failed");reply(out,"200 OK",response.toString());
    }
}
