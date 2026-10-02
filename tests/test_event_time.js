const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(require('path').join(__dirname,'../app.js'),'utf8');
const code=src.slice(src.indexOf('function eventAvailable('),src.indexOf('function countdown('));
const ctx={Intl,Date};vm.createContext(ctx);vm.runInContext(code,ctx);
const now=new Date('2026-10-02T16:01:00Z'); // Shanghai already October 3
const x={category:'论坛 / 展会',event_date:'2026-10-03'};
assert(ctx.eventAvailable(x,now));
assert(!ctx.eventAvailable({...x,event_date:'2026-10-02'},now));
assert(!ctx.eventAvailable({...x,deadline:'2026-10-03T00:00:00'},now));
assert(ctx.eventAvailable({...x,deadline:'2026-10-03T01:00:00'},now));
assert(!ctx.eventAvailable({...x,event_date:undefined},now));
console.log('offline event date and timezone tests passed');

