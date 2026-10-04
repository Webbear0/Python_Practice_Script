// 带 data-confirm 属性的表单，提交前弹窗确认
// （CSP 禁止内联脚本，所以不能写 onsubmit="..."，统一在这里处理）
document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute("data-confirm");
    if (msg && !confirm(msg)) {
        e.preventDefault();
    }
});
