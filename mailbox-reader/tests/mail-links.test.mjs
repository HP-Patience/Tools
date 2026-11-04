import test from 'node:test';
import assert from 'node:assert/strict';
import { findLinks } from '../static/mail-links.js';

test('extracts exact verification URL and keeps footer links separate', () => {
  const url='https://arena.ai/nextjs-api/callback/email?token=TEST_TOKEN&type=email&signup_intent_id=test-id';
  const text=`Verify Email<${url}>\r\nHow it Works<https://arena.ai/how-it-works> About Us<https://arena.ai/about>`;
  const links=findLinks(text);
  assert.equal(links.length,3);
  assert.equal(links[0].url,url);
  assert.equal(links[0].verification,true);
  assert.equal(links[1].verification,false);
  assert.equal(links[2].verification,false);
  for(const link of links) assert.equal(text.slice(link.start,link.end),link.url);
});
test('allows HTTP(S) only and does not interpret HTML or script URLs',()=>{
  const links=findLinks('<script>alert(1)</script> javascript:alert(2) data:text/html,evil mailto:me@example.com https://example.com/a?x=1&y=2');
  assert.equal(links.length,1);
  assert.equal(links[0].url,'https://example.com/a?x=1&y=2');
});
test('handles punctuation, balanced parentheses, case and duplicates',()=>{
  const text='See (https://example.com/file_(a)).\nHTTPS://example.com/confirm?code=123， https://example.com/confirm?code=123';
  const links=findLinks(text);
  assert.equal(links.length,3);
  assert.equal(links[0].url,'https://example.com/file_(a)');
  assert.equal(links[1].verification,true);
  assert.equal(links[2].verification,true);
});
test('recognizes button labels and common verification paths without treating management links as verification',()=>{
  const text='确认邮箱<https://example.com/action?code=123>\nManage apps<https://account.live.com/consent/Manage?fn=email>\nhttps://example.com/verify-email?code=test';
  const links=findLinks(text);
  assert.equal(links[0].verification,true);
  assert.equal(links[1].verification,false);
  assert.equal(links[2].verification,true);
});
test('rejects URL userinfo and ignores malformed URLs',()=>{
  assert.equal(findLinks('https:// https://user:pass@example.com/path').length,0);
});
