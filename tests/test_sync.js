const assert=require("assert");
const C=require("../sync-core.js");

(function testSetMergeLatestWins(){
  let a=C.emptyState(), b=C.emptyState();
  a=C.touchSet(a,"saved","x",true,100);
  b=C.touchSet(b,"saved","x",false,200);
  const m=C.merge(a,b);
  assert.strictEqual(m.sets.saved.x.present,false);
  assert.strictEqual(m.sets.saved.x.ts,200);
})();

(function testUnionDifferentKeys(){
  let a=C.emptyState(), b=C.emptyState();
  a=C.touchSet(a,"read","a",true,100);
  b=C.touchSet(b,"read","b",true,110);
  const m=C.merge(a,b);
  assert.deepStrictEqual(new Set(C.presentKeys(m.sets.read)),new Set(["a","b"]));
})();

(function testBlobLatestWins(){
  let a=C.emptyState(), b=C.emptyState();
  a=C.touchBlob(a,"mode","5min",100);
  b=C.touchBlob(b,"mode","10min",120);
  const m=C.merge(a,b);
  assert.strictEqual(m.blobs.mode.value,"10min");
})();

(function testDeletionPropagates(){
  let a=C.emptyState(), b=C.emptyState();
  a=C.touchSet(a,"watchlist","Godot",true,100);
  b=C.touchSet(b,"watchlist","Godot",false,300);
  const m=C.merge(a,b);
  assert.deepStrictEqual(C.presentKeys(m.sets.watchlist),[]);
})();

console.log("sync merge tests passed");
