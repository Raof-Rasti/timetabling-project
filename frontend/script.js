async function send() {
  const file = document.getElementById("file_excel").files[0];
  if (!file) {
    alert("فایل را انتخاب کنید");
    return;
  }

  const fd = new FormData();
  fd.append("file_excel", file);

  const res = await fetch("/api/schedule", {
    method: "POST",
    body: fd
  });

  const data = await res.json();
  if (data.error) {
    alert(data.error);
    return;
  }

  const container = document.getElementById("results");
  container.innerHTML = "";

  buildTable("⏰ تایم‌های یک کلاس", data.one_class);
  buildTable("🏫 تایم‌های همه کلاس‌ها", data.all_classes);
  buildTable("👨‍🏫 تایم‌های یک استاد", data.one_teacher);
  buildTable("👥 تایم‌های همه اساتید", data.all_teachers);
}


function buildTable(title, rows) {
  const card = document.createElement("div");
  card.className = "card";

  const h = document.createElement("h3");
  h.textContent = title;
  card.appendChild(h);

  const table = document.createElement("table");

  if (rows.length === 0) {
    table.innerHTML = "<tr><td>داده‌ای موجود نیست</td></tr>";
    card.appendChild(table);
    return;
  }

  const headers = Object.keys(rows[0]);
  table.innerHTML += `<tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr>`;

  rows.forEach((row, i) => {
    const tr = document.createElement("tr");
    if (i > 0) tr.classList.add("blur");
    tr.innerHTML = headers.map(h => `<td>${row[h]}</td>`).join("");
    table.appendChild(tr);
  });

  card.appendChild(table);
  document.getElementById("results").appendChild(card);
}
