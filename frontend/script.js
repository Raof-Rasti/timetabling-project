const form = document.getElementById('uploadForm');
const errBox = document.getElementById('error');
const resultBox = document.getElementById('result');
const tablesContainer = document.getElementById('tables-container');

function buildTable(title, rows) {
  const section = document.createElement('div');
  section.className = 'table-wrapper';
  const heading = document.createElement('h3');
  heading.textContent = title;

  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const tbody = document.createElement('tbody');

  if (!rows || rows.length === 0 || (rows[0] && rows[0].error)) {
    thead.innerHTML = '';
    tbody.innerHTML = `<tr><td>❌ خطا یا داده‌ای موجود نیست</td></tr>`;
  } else {
    const headers = Object.keys(rows[0]);
    thead.innerHTML = `<tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>`;
    tbody.innerHTML = rows
      .map(r => `<tr>${headers.map(h => `<td>${r[h] ?? ''}</td>`).join('')}</tr>`)
      .join('');
  }

  table.appendChild(thead);
  table.appendChild(tbody);
  section.appendChild(heading);
  section.appendChild(table);
  tablesContainer.appendChild(section);
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  errBox.classList.add('hidden');
  resultBox.classList.remove('hidden');
  tablesContainer.innerHTML = '<p>⏳ در حال پردازش فایل‌ها...</p>';

  const body = new FormData();
  const f1 = document.getElementById('file_teacher').files[0];
  const f2 = document.getElementById('file_all_teachers').files[0];
  const f3 = document.getElementById('file_class').files[0];
  const f4 = document.getElementById('file_all_classes').files[0];

  if (!f1 || !f2 || !f3 || !f4) {
    tablesContainer.innerHTML = '';
    errBox.textContent = 'لطفاً هر چهار فایل اکسل را انتخاب کنید.';
    errBox.classList.remove('hidden');
    return;
  }

  body.append('file_teacher', f1);
  body.append('file_all_teachers', f2);
  body.append('file_class', f3);
  body.append('file_all_classes', f4);

  try {
    // relative path → same origin → avoids CORS & 404
    const res = await fetch('/api/schedule', { method: 'POST', body });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'خطا در پردازش فایل‌ها');

    tablesContainer.innerHTML = '';
    buildTable('📘 برنامهٔ یک استاد', data.teacher_schedule);
    buildTable('👨‍🏫 همهٔ اساتید', data.all_teachers);
    buildTable('🏫 یک کلاس', data.class_schedule);
    buildTable('🏢 همهٔ کلاس‌ها', data.all_classes);
  } catch (err) {
    tablesContainer.innerHTML = '';
    errBox.textContent = err.message;
    errBox.classList.remove('hidden');
  }
});
