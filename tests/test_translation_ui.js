// Run with Playwright available on NODE_PATH; BROWSER_EXECUTABLE is optional.
const {chromium,devices}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const root=path.resolve(__dirname,'..');
const server=http.createServer((req,res)=>{
  let target=path.resolve(root,'.'+req.url.split('?')[0]);
  if(fs.existsSync(target)&&fs.statSync(target).isDirectory())target=path.join(target,'index.html');
  if(!target.startsWith(root+path.sep)||!fs.existsSync(target)){res.writeHead(404);return res.end();}
  res.setHeader('Content-Type',({'.js':'text/javascript','.css':'text/css','.html':'text/html','.json':'application/json'})[path.extname(target)]||'application/octet-stream');res.end(fs.readFileSync(target));
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
  try{
    for(const [name,options] of [['电脑',{viewport:{width:1440,height:1000}}],['iPhone',devices['iPhone 13']],['iPad',devices['iPad Pro 11']]]){
      const context=await browser.newContext({...options,serviceWorkers:'block'});
      const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
      const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
      const items=[1,2].map(i=>({id:'translation-ui-'+i,title:'New video model introduces camera control '+i,summary:'This update adds reference video and camera control for creators.',why:'新增参考视频和镜头控制能力。',url:'https://example.org/article/'+i,source:'测试来源',category:'AI 影视',published_at:today,date_confidence:'high',score:140,tier:'必看',alternatives:[{source:'其他来源',url:'https://example.org/alternate/'+i}]}));
      const issue={...JSON.parse(fs.readFileSync(path.join(root,'data/latest_10min.json'))),date:today,top3:items,sections:[]};
      await page.route('**/data/latest*.json',route=>route.fulfill({json:issue}));
      await page.route('**/data/today.json',route=>route.fulfill({json:{date:today,items}}));
      await page.route('**/data/category_news.json',route=>route.fulfill({json:{items:[]}}));
      await page.goto('http://127.0.0.1:'+server.address().port+'/');
      const card=page.locator('#top3 [data-article-id="translation-ui-1"]');
      await card.waitFor();
      await card.locator('.story-details > summary').click();
      await card.locator('.alts > summary').click();
      await page.evaluate(()=>{
        window.translationTestCard=document.querySelector('#top3 [data-article-id="translation-ui-1"]');
        window.translationTestDetails=window.translationTestCard.querySelector('.story-details');
        window.translationTestButton=window.translationTestCard.querySelector('.translate-btn');
        window.AIBriefTranslate.article=()=>new Promise(resolve=>window.finishTranslation=resolve);
      });
      const button=card.locator('.translate-btn');
      await button.click();assert.equal(await button.textContent(),'翻译中…');assert(await button.isDisabled());
      const intact=()=>page.evaluate(()=>translationTestCard===document.querySelector('#top3 [data-article-id="translation-ui-1"]')&&translationTestDetails.open&&translationTestCard.querySelector('.alts').open&&translationTestButton===translationTestCard.querySelector('.translate-btn'));
      assert(await intact());
      await page.evaluate(()=>finishTranslation({title:'新视频模型更新镜头控制',summary:'新增参考视频和镜头控制，支持创作者制作视频。'}));
      await page.waitForFunction(()=>document.querySelector('#top3 [data-article-id="translation-ui-1"] h4').textContent==='新视频模型更新镜头控制');
      assert(await intact());assert.equal(await button.textContent(),'显示原文');
      assert.equal(await card.locator('.brief-parts > div:first-child p').textContent(),'新增参考视频和镜头控制，支持创作者制作视频。');
      const closed=page.locator('#top3 [data-article-id="translation-ui-2"] .story-details');
      assert.equal(await closed.getAttribute('open'),null);
      await button.click();assert(await intact());assert((await card.locator('h4').textContent()).startsWith('New video model'));
      await button.click();assert(await intact());assert.equal(await button.textContent(),'显示原文');
      await closed.locator(':scope > summary').click();
      await page.evaluate(()=>window.AIBriefTranslate.article=async()=>{throw Error('测试翻译服务暂不可用');});
      const other=page.locator('#top3 [data-article-id="translation-ui-2"]');
      await other.locator('.translate-btn').click();await other.locator('.translation-error').waitFor();
      assert.notEqual(await closed.getAttribute('open'),null);assert(await intact());
      await page.evaluate(()=>window.AIBriefTranslate.article=async()=>({title:'第二条中文资讯',summary:'重试成功，详情仍然展开。'}));
      await other.locator('.translate-btn').click();
      await page.waitForFunction(()=>document.querySelector('#top3 [data-article-id="translation-ui-2"] h4').textContent==='第二条中文资讯');
      assert.equal(await other.locator('.translation-error').count(),0);assert.notEqual(await closed.getAttribute('open'),null);
      assert.equal(new URL(page.url()).pathname,'/');assert.deepEqual(errors,[]);
      if(process.env.TRANSLATION_SCREENSHOTS){await card.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.TRANSLATION_SCREENSHOTS,name+'-原处翻译.png')});}
      await context.close();console.log(name+': translation keeps article, expanded details and nested sources intact; original toggle and failure retry passed');
    }
  }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
