const {chromium,devices}=require('playwright');
const http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..'),errors=[];
const server=http.createServer((req,res)=>{
 let p=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));if(!p.startsWith(root+path.sep)&&p!==root){res.writeHead(403);return res.end()}
 if(fs.existsSync(p)&&fs.statSync(p).isDirectory())p=path.join(p,'index.html');
 if(!fs.existsSync(p)){res.writeHead(404);return res.end()}
 const types={'.js':'text/javascript','.json':'application/json','.html':'text/html','.css':'text/css','.png':'image/png','.webmanifest':'application/manifest+json'};
 res.setHeader('Content-Type',types[path.extname(p)]||'text/plain');res.end(fs.readFileSync(p));
});
(async()=>{
 await new Promise(r=>server.listen(8765,'127.0.0.1',r));
 const browser=await chromium.launch({...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{}),headless:true});
 try{
 for(const [name,opts] of [['desktop',{viewport:{width:1440,height:960}}],['iphone',devices['iPhone 13']],['ipad',devices['iPad Pro 11']]]){
  const context=await browser.newContext({...opts,defaultBrowserType:undefined});const page=await context.newPage();page.on('pageerror',e=>errors.push(name+': '+e.message));
  await page.goto('http://127.0.0.1:8765/');await page.waitForSelector('.card');
  await page.locator('.save').first().click();assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('ai-brief-saved')).length),1);
  await page.locator('#mode5').click();await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>localStorage.getItem('ai-brief-mode')),'5min');
  await page.evaluate(async()=>{await navigator.serviceWorker.ready});
  await page.reload();await page.waitForSelector('.card');await context.setOffline(true);await page.reload();await page.waitForSelector('.card');
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('ai-brief-saved')).length),1);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2),false,name+' horizontal overflow');
  await page.screenshot({path:path.join(root,'dist',name+'-offline.png'),fullPage:true});await context.close();console.log(name+': render, save, 5min, offline reload passed');
 }
 assert.deepEqual(errors,[]);console.log('browser checks passed (Edge/Chromium device emulation; not physical iOS Safari)');
 }finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
