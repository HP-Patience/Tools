import test from 'node:test';
import assert from 'node:assert/strict';
import { copyText } from '../static/clipboard.js';

test('copy supports missing clipboard and denied permission', async()=>{
  const original = Object.getOwnPropertyDescriptor(globalThis,'navigator');
  const originalDocument=globalThis.document;
  const originalWindow=globalThis.window;
  let selected='',removed=0,prompted=0;
  const field={style:{},setAttribute(){},focus(){},select(){selected=this.value;},setSelectionRange(){},remove(){removed++;}};
  let success=true;
  globalThis.document={activeElement:{focus(){}},createElement:()=>field,querySelector:()=>null,body:{append(){}},execCommand:()=>success};
  globalThis.window={prompt(){prompted++;}};
  try {
    Object.defineProperty(globalThis,'navigator',{configurable:true,value:{}});
    await copyText('demo@example.com');
    assert.equal(selected,'demo@example.com');
    Object.defineProperty(globalThis,'navigator',{configurable:true,value:{clipboard:{writeText:async()=>{throw new Error('denied');}}}});
    await copyText('verification-url');
    assert.equal(selected,'verification-url');
    success=false;
    await assert.rejects(copyText('manual-copy'),/手动复制/);
    assert.equal(prompted,1);
    assert.equal(removed,3);
    let native='';
    Object.defineProperty(globalThis,'navigator',{configurable:true,value:{clipboard:{writeText:async text=>{native=text;}}}});
    await copyText('native-copy');
    assert.equal(native,'native-copy');
    assert.equal(removed,3);
  } finally {
    if(original) Object.defineProperty(globalThis,'navigator',original); else delete globalThis.navigator;
    globalThis.document=originalDocument; globalThis.window=originalWindow;
  }
});
