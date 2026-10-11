// 带 data-confirm 属性的表单，提交前弹窗确认
// （CSP 禁止内联脚本，所以不能写 onsubmit="..."，统一在这里处理）
document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute("data-confirm");
    if (msg && !confirm(msg)) {
        e.preventDefault();
    }
});

// 建表页的"添加字段"按钮：复制最后一行，清空内容
// 复选框的 value 是行号，新行要换成新的行号，后端才能对应上
document.addEventListener("click", function (e) {
    var bodyId = e.target.getAttribute("data-add-row");
    if (!bodyId) return;
    var body = document.getElementById(bodyId);
    var row = body.rows[body.rows.length - 1].cloneNode(true);
    var index = body.rows.length;
    row.querySelectorAll("input").forEach(function (el) {
        if (el.type === "checkbox") {
            el.checked = el.name === "null";  // 新字段默认允许 NULL
            el.value = index;
        } else {
            el.value = "";
        }
    });
    row.querySelector("select").value = "VARCHAR";
    body.appendChild(row);
});
