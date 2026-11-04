export async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch { /* Try the compatible copy path if clipboard permission is denied. */ }
  const focused = document.activeElement;
  const field = document.createElement('textarea');
  field.value = text;
  field.readOnly = true;
  field.setAttribute('aria-label', '待复制内容');
  field.style.cssText = 'position:fixed;left:0;top:0;width:1px;height:1px;opacity:0;';
  // Keep the field inside an open modal so it can receive focus.
  (document.querySelector('dialog[open]') || document.body).append(field);
  let copied = false;
  try {
    field.focus({preventScroll:true});
    field.select();
    field.setSelectionRange(0, text.length);
    copied = document.execCommand('copy');
  } catch { /* Show selectable text when the browser blocks both methods. */ }
  finally {
    field.remove();
    focused?.focus({preventScroll:true});
  }
  if (!copied) {
    window.prompt('浏览器未允许自动复制，请复制下面的内容：', text);
    throw new Error('自动复制未成功，请在弹窗中手动复制');
  }
}
