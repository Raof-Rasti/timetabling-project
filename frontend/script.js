const form = document.getElementById('uploadForm');
const resultBox = document.getElementById('result');
const errBox = document.getElementById('error');
const softScoreEl = document.getElementById('softScore');
const countSessionsEl = document.getElementById('countSessions');
const countHardEl = document.getElementById('countHard');
const countSoftEl = document.getElementById('countSoft');
const downloadLink = document.getElementById('downloadLink');
const previewTable = document.getElementById('previewTable');

function buildTable(rows) {
  if (!rows || rows.length === 0) {
    previewTable.tHead.innerHTML = '';
    previewTable.tBodies[0].innerHTML = '<tr><td>داده‌ای موجود نیست</td></tr>';
    return;
  }
  const headers = Object.keys(rows[0]);
  const thead = '<tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr>';
  const tbody = rows.map(r => '<tr>' + headers.map(h => `<td>${r[h] ?? ''}</td>`).join('') + '</tr>').join('');
  previewTable.tHead.innerHTML = thead;
  previewTable.tBodies[0].innerHTML = tbody;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  errBox.classList.add('hidden');
  const file = document.getElementById('file').files[0];
  if (!file) { return; }

  const body = new FormData();
  body.append('file', file);

  try {
    const res = await fetch(`${window.API_BASE}/api/schedule`, {
      method: 'POST',
      body
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'خطا در سرویس');

    softScoreEl.textContent = data.soft_score.toFixed(2);
    countSessionsEl.textContent = data.counts.sessions;
    countHardEl.textContent = data.counts.hard_errors;
    countSoftEl.textContent = data.counts.soft_details;

    downloadLink.href = `${window.API_BASE}/api/download/${data.token}`;
    downloadLink.setAttribute('download', 'schedule_output.xlsx');

    buildTable(data.preview);
    resultBox.classList.remove('hidden');
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove('hidden');
  }
});


