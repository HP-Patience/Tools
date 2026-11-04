'use strict';
export function findLinks(text) {
  const links=[];
  for (const match of text.matchAll(/https?:\/\/[^\s<>"'，。；！？、]+/gi)) {
    let url=match[0].replace(/[.,;!?]+$/, '');
    for (const [open,close] of [['(',')'],['[',']'],['{','}']]) {
      while (url.endsWith(close) && url.split(close).length > url.split(open).length) url=url.slice(0,-1);
    }
    let parsed;
    try { parsed=new URL(url); } catch { continue; }
    if (!['http:','https:'].includes(parsed.protocol) || parsed.username || parsed.password) continue;
    const label=text.slice(Math.max(0,match.index-100),match.index).split(/[>\r\n]/).pop().replace(/[<\s:：]+$/, '').trim();
    const verification=/(?:verif(?:y|ication)|confirm|activat(?:e|ion)|验证|確認|确认|激活)/i.test(parsed.pathname)
      || /(?:verif(?:y|ication)|confirm|activat(?:e|ion)|验证|確認|确认|激活)/i.test(label)
      || (/(?:callback|auth)/i.test(parsed.pathname) && parsed.searchParams.get('type')==='email');
    links.push({url,start:match.index,end:match.index+url.length,verification});
  }
  return links;
}
