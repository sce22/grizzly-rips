(() => {
  const app = document.getElementById("app");
  const cache = {};
  let INDEX = null;
  let seasonFilter = "All";
  let selectedDays = new Set();
  let calMonth = null; // "YYYY-MM"

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const slug = (n) => n.replace(/[^A-Za-z0-9]/g, "_").toLowerCase();
  const fmtDate = (ts) => new Date(ts * 1000).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  const fmtTime = (ts) => new Date(ts * 1000).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const pct = (v) => (v == null ? "–" : `${Math.round(v)}%`);
  const TYPE = { leagueMatch: "League", playoffMatch: "Playoff", friendlyMatch: "Friendly" };

  async function load(path) {
    if (!cache[path]) cache[path] = fetch(path, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(path); return r.json(); });
    return cache[path];
  }

  function textOn(hex) {
    const n = parseInt(hex.replace("#", ""), 16);
    const [r, g, b] = [n >> 16, (n >> 8) & 255, n & 255].map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? "#111" : "#fff";
  }

  function ratingColor(r) {
    if (r >= 8.5) return "#0e7a3a";
    if (r >= 7.5) return "#2f9e44";
    if (r >= 6.8) return "#8a9a1b";
    if (r >= 6.0) return "#c27c0e";
    return "#c0392b";
  }

  function applyBrand(club) {
    const root = document.documentElement.style;
    root.setProperty("--primary", club.colors.primary);
    root.setProperty("--secondary", club.colors.secondary);
    root.setProperty("--on-primary", textOn(club.colors.primary));
    root.setProperty("--on-secondary", textOn(club.colors.secondary));
    const initials = club.name.split(/\s+/).map((w) => w[0]).join("").slice(0, 3);
    const crest = club.logo
      ? `<img class="crest" src="${esc(club.logo)}" alt="${esc(club.name)} crest" onerror="this.outerHTML='<div class=\\'crest fallback\\'>${esc(initials)}</div>'">`
      : `<div class="crest fallback">${esc(initials)}</div>`;
    const rec = INDEX.matches.reduce((a, m) => (a[m.result]++, a), { W: 0, D: 0, L: 0 });
    document.getElementById("masthead").innerHTML = `
      <div class="inner">
        <a href="#/">${crest}</a>
        <div>
          <h1>${esc(club.name)}</h1>
          <div class="sub">${club.stadium ? esc(club.stadium) + " · " : ""}${INDEX.matches.length} matches logged</div>
          <div class="record"><span>W ${rec.W}</span><span>D ${rec.D}</span><span>L ${rec.L}</span></div>
        </div>
      </div>`;
  }

  // ------------------------------------------------------------- views

  // ------------------------------------------------------------ calendar

  const pad2 = (n) => String(n).padStart(2, "0");
  const dayKey = (ts) => { const d = new Date(ts * 1000); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`; };
  const monthKey = (ts) => dayKey(ts).slice(0, 7);
  const recordOf = (ms) => ms.reduce((a, m) => (a[m.result]++, a.n++, a.gf += m.gf, a.ga += m.ga, a), { W: 0, D: 0, L: 0, n: 0, gf: 0, ga: 0 });
  const recText = (r) => `${r.W}W ${r.D}D ${r.L}L`;

  function shiftMonth(key, delta) {
    const [y, m] = key.split("-").map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}`;
  }

  function calendarHTML(pool) {
    const byDay = {};
    pool.forEach((m) => (byDay[dayKey(m.ts)] ||= []).push(m));
    const max = Math.max(1, ...Object.values(byDay).map((ms) => ms.length));
    const [y, mo] = calMonth.split("-").map(Number);
    const lead = new Date(y, mo - 1, 1).getDay();
    const days = new Date(y, mo, 0).getDate();
    const today = dayKey(Date.now() / 1000);
    const starts = Object.fromEntries((INDEX.season_starts || []).map((s) => [s.date, s.short]));
    const monthGames = pool.filter((m) => monthKey(m.ts) === calMonth);
    const allMonths = INDEX.matches.map((m) => monthKey(m.ts));
    const minMonth = allMonths.length ? allMonths.reduce((a, b) => (a < b ? a : b)) : calMonth;
    const maxMonth = [today.slice(0, 7), ...allMonths].reduce((a, b) => (a > b ? a : b));

    const cells = [];
    for (let i = 0; i < lead; i++) cells.push(`<span class="cal-day blank" aria-hidden="true"></span>`);
    for (let d = 1; d <= days; d++) {
      const key = `${calMonth}-${pad2(d)}`;
      const ms = byDay[key] || [];
      const r = recordOf(ms);
      const heat = ms.length ? 0.18 + 0.62 * (ms.length / max) : 0;
      const label = new Date(y, mo - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
      const season = starts[key] ? `<i class="cal-season" title="Season starts">${esc(starts[key])}</i>` : "";
      if (!ms.length) {
        cells.push(`<span class="cal-day empty${key === today ? " today" : ""}" aria-label="${label}: no games">${season}<b>${d}</b></span>`);
        continue;
      }
      const bar = ["W", "D", "L"].filter((k) => r[k]).map((k) => `<i class="seg ${k}" style="flex:${r[k]}"></i>`).join("");
      cells.push(`<button type="button" class="cal-day has${heat > 0.5 ? " dark" : ""}${selectedDays.has(key) ? " on" : ""}${key === today ? " today" : ""}"
        style="--heat:${(heat * 100).toFixed(0)}%" data-day="${key}" aria-pressed="${selectedDays.has(key)}"
        aria-label="${label}: ${ms.length} game${ms.length > 1 ? "s" : ""}, ${r.W} won, ${r.D} drawn, ${r.L} lost">
        ${season}<b>${d}</b><span class="cal-rec">${r.W}-${r.D}-${r.L}</span><span class="cal-bar">${bar}</span></button>`);
    }
    const mr = recordOf(monthGames);
    const monthName = new Date(y, mo - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
    return `
      <section class="card cal" aria-label="Match calendar">
        <div class="cal-head">
          <button type="button" class="cal-nav" data-cal="-1" aria-label="Previous month" ${calMonth <= minMonth ? "disabled" : ""}>‹</button>
          <div><b>${monthName}</b><small>${mr.n ? `${mr.n} game${mr.n > 1 ? "s" : ""} · ${recText(mr)}` : "No games"}</small></div>
          <button type="button" class="cal-nav" data-cal="1" aria-label="Next month" ${calMonth >= maxMonth ? "disabled" : ""}>›</button>
        </div>
        <div class="cal-grid">
          ${["S", "M", "T", "W", "T", "F", "S"].map((w) => `<span class="cal-dow">${w}</span>`).join("")}
          ${cells.join("")}
        </div>
        <div class="cal-legend">
          <span><i class="sw" style="--heat:25%"></i><i class="sw" style="--heat:50%"></i><i class="sw" style="--heat:80%"></i> more games</span>
          <span><i class="dot W"></i>W <i class="dot D"></i>D <i class="dot L"></i>L</span>
          <span class="cal-hint">Tap days to filter</span>
        </div>
      </section>`;
  }

  function matchesView() {
    if (!calMonth) calMonth = INDEX.matches.length ? monthKey(INDEX.matches[0].ts) : dayKey(Date.now() / 1000).slice(0, 7);
    const seasons = ["All", ...new Set(INDEX.matches.map((m) => m.season))];
    const pool = INDEX.matches.filter((m) => seasonFilter === "All" || m.season === seasonFilter);
    const list = selectedDays.size ? pool.filter((m) => selectedDays.has(dayKey(m.ts))) : pool;
    const groups = {};
    list.forEach((m) => (groups[m.season] ||= []).push(m));
    const chips = seasons.map((s) => `<button type="button" class="chip ${s === seasonFilter ? "on" : ""}" data-season="${esc(s)}">${esc(s.split(" · ")[0])}</button>`).join("");
    const sel = [...selectedDays].sort();
    const selRec = recordOf(list);
    const selection = sel.length ? `
      <div class="selection">
        <div><b>${sel.length === 1 ? new Date(sel[0] + "T12:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }) : `${sel.length} days`}</b>
          <span>${selRec.n} game${selRec.n === 1 ? "" : "s"} · ${recText(selRec)} · ${selRec.gf} scored, ${selRec.ga} conceded</span></div>
        <button type="button" class="chip" id="clear-days">Clear</button>
      </div>` : "";
    const body = Object.entries(groups).map(([season, ms]) => {
      const r = recordOf(ms);
      return `<div class="season-head"><h2>${esc(season)}</h2><small>${recText(r)}</small></div>` +
        ms.map((m) => `
          <a class="card match-row" href="#/match/${m.id}">
            <span class="pill ${m.result}">${m.result}</span>
            <div>
              <div class="when">${fmtDate(m.ts)} · ${fmtTime(m.ts)} · ${TYPE[m.type] || m.type}</div>
              <div class="opp">vs ${esc(m.opponent)}</div>
              ${m.top ? `<div class="top">★ ${esc(m.top.name)} ${m.top.rating.toFixed(1)}</div>` : ""}
            </div>
            <div class="score">${m.gf} – ${m.ga}</div>
          </a>`).join("");
    }).join("");
    app.innerHTML = `<div class="chips">${chips}</div>${calendarHTML(pool)}${selection}${body || `<div class="empty">No matches yet. Play a game and check back soon.</div>`}`;
    app.querySelectorAll("[data-season]").forEach((b) => b.onclick = () => {
      seasonFilter = b.dataset.season;
      selectedDays.clear();
      const first = INDEX.matches.find((m) => seasonFilter === "All" || m.season === seasonFilter);
      if (first) calMonth = monthKey(first.ts);
      matchesView();
    });
    app.querySelectorAll("[data-cal]").forEach((b) => b.onclick = () => { calMonth = shiftMonth(calMonth, Number(b.dataset.cal)); matchesView(); });
    app.querySelectorAll("[data-day]").forEach((b) => b.onclick = () => {
      const k = b.dataset.day;
      selectedDays.has(k) ? selectedDays.delete(k) : selectedDays.add(k);
      matchesView();
    });
    document.getElementById("clear-days")?.addEventListener("click", () => { selectedDays.clear(); matchesView(); });
  }

  function statCell(value, label, extra = "") {
    return `<div class="stat"><b>${value}</b><span>${label}</span>${extra ? `<em>${extra}</em>` : ""}</div>`;
  }

  function statGrid(p) {
    const s = p.stats;
    const cells = [];
    if (p.pos === "goalkeeper") {
      cells.push(statCell(s.saves, "Saves"), statCell(pct(s.save_pct), "Save %"), statCell(s.conceded, "Conceded"));
    }
    cells.push(
      statCell(`${s.passes_made}/${s.passes_att}`, "Passes", pct(s.pass_pct)),
      statCell(s.goals, "Goals"), statCell(s.assists, "Assists"),
      statCell(s.shots_on != null ? `${s.shots_on}/${s.shots}` : s.shots, s.shots_on != null ? "On target" : "Shots", s.shots ? `${pct(s.conversion)} scored` : ""),
      statCell(s.key_passes ?? "–", "Key passes"),
      statCell(`${s.tackles_made}/${s.tackles_att}`, "Tackles", pct(s.tackle_pct)),
    );
    if (s.red_cards) cells.push(statCell("🟥", "Red card"));
    return `<div class="statgrid">${cells.join("")}</div>`;
  }

  function driversBlock(impact) {
    const max = Math.max(0.5, ...impact.drivers.map((d) => Math.abs(d.impact)));
    const rows = impact.drivers.map((d) => {
      const w = (Math.abs(d.impact) / max) * 50;
      const cls = d.impact >= 0 ? "pos" : "neg";
      const label = d.count != null && d.key !== "result_val" && d.key !== "clean_sheet" ? `${esc(d.label)} (${d.count})` : esc(d.label);
      return `<div class="driver"><span>${label}</span><div class="bar"><div class="fill ${cls}" style="width:${w}%"></div></div><span class="val ${cls}">${d.impact > 0 ? "+" : ""}${d.impact.toFixed(2)}</span></div>`;
    }).join("");
    return `<div class="drivers">${rows}</div>
      <div class="model-note">Starts from a ${impact.baseline.toFixed(1)} base. "Everything else" is rating EA doesn't itemise (positioning, dribbles, interceptions). ${impact.share != null ? `Weights are ${Math.round(impact.share * 100)}% learned from Grizzly Rips matches and ${100 - Math.round(impact.share * 100)}% league baseline, shifting toward your own data every match.` : (impact.learned ? "Weights learned from your club's own matches." : "Using league baseline weights.")}</div>`;
  }

  function playerCard(p, open) {
    const strengths = p.strengths.map((s) => `<div class="note good"><b>${esc(s.title)}</b>${s.coach ? `<p class="say">${esc(s.coach)}</p>` : ""}<small>${esc(s.detail)}</small></div>`).join("");
    const weaknesses = p.weaknesses.map((w) => `
      <div class="note bad"><b>${esc(w.title)}</b>${w.coach ? `<p class="say">${esc(w.coach)}</p>` : ""}<small>${esc(w.detail)}</small>
        <div class="drill-label">Coach's drill</div>
        <ul class="tips">${w.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></div>`).join("");
    const vs = p.vs_average != null ? ` · ${p.vs_average >= 0 ? "▲" : "▼"} ${Math.abs(p.vs_average).toFixed(1)} vs avg` : "";
    return `
      <details class="card pcard" id="p-${slug(p.name)}" ${open ? "open" : ""}>
        <summary>
          <div class="rating" style="background:${ratingColor(p.stats.rating)}">${p.stats.rating.toFixed(1)}</div>
          <div>
            <div class="pname">${esc(p.name)}${p.stats.mom ? " ⭐" : ""}</div>
            <div class="ppos"><span class="cap">${esc(p.pos)}</span> · ${p.stats.minutes}'${vs}</div>
            ${p.band ? `<span class="band band-${p.band.split(" ")[0].toLowerCase()}">${esc(p.band)}</span>` : ""}
          </div>
          <svg class="chev" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
        </summary>
        <div class="pbody">
          <p class="coach-say">${esc(p.coach ? p.coach.opener : p.headline)}</p>
          ${statGrid(p)}
          <div class="section-label">What moved the rating</div>
          ${driversBlock(p.impact)}
          ${strengths ? `<div class="section-label">Did well</div>${strengths}` : ""}
          ${weaknesses ? `<div class="section-label">To work on</div>${weaknesses}` : ""}
          ${p.coach ? `<p class="coach-say closer">${esc(p.coach.closer)} <span>- ${esc(p.coach.name || "Coach Lasso")}</span></p>` : ""}
          <a class="back" href="#/player/${encodeURIComponent(p.name)}">Full profile & trends →</a>
        </div>
      </details>`;
  }

  function talkCard(talk) {
    const item = (x, i) => `<li><b>${esc(x.title)}</b><span>${esc(x.line)}</span>${x.tip ? `<em>${esc(x.tip)}</em>` : ""}</li>`;
    return `
      <section class="card talk" aria-label="Coach's team talk">
        <div class="talk-head"><span class="whistle" aria-hidden="true">📣</span><div><h3>Coach's team talk</h3><p class="coach-say">${esc(talk.opener)}</p></div></div>
        <div class="talk-cols">
          <div><div class="section-label good-label">What we did well</div><ol class="talk-list good">${talk.well.map(item).join("")}</ol></div>
          <div><div class="section-label bad-label">Work on next match</div><ol class="talk-list bad">${talk.work_on.map(item).join("")}</ol></div>
        </div>
        <p class="coach-say closer">${esc(talk.signoff.replace(/ - Coach$/, ""))} <span>- ${esc(talk.coach || "Coach Lasso")}</span></p>
      </section>`;
  }

  async function matchView(id, focus) {
    const m = await load(`data/matches/${id}.json`);
    const t = m.team;
    app.innerHTML = `
      <a class="back" href="#/">← All matches</a>
      <div class="card scoreboard">
        <div class="teams">
          <div class="team">${esc(INDEX.club.short_name)}</div>
          <div class="big">${m.gf} – ${m.ga}</div>
          <div class="team">${esc(m.opponent.name)}</div>
        </div>
        <div class="meta"><span class="pill ${m.result}" style="width:auto;padding:0 8px;height:22px">${{ W: "WIN", D: "DRAW", L: "LOSS" }[m.result]}</span>
          &nbsp;${fmtDate(m.ts)} ${fmtTime(m.ts)} · ${TYPE[m.type] || m.type} · ${esc(m.season)}${m.dnf ? " · DNF" : ""}</div>
        <div class="team-stats">
          <div><b>${t.shots_on != null ? `${t.shots_on}/${t.shots}` : t.shots}</b><span>On target</span></div>
          <div><b>${pct(t.pass_pct)}</b><span>Pass acc.</span></div>
          <div><b>${pct(t.tackle_pct)}</b><span>Tackles won</span></div>
          <div><b>${t.key_passes ?? "–"}</b><span>Key passes</span></div>
        </div>
      </div>
      ${m.talk ? talkCard(m.talk) : ""}
      <h2>Player breakdowns</h2>
      ${m.players.map((p) => playerCard(p, focus ? p.name === focus : false)).join("") || `<div class="empty">No human players recorded.</div>`}`;
    if (focus) document.getElementById(`p-${slug(focus)}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function squadView() {
    app.innerHTML = `<h2>Squad</h2>` + INDEX.players.map((p) => {
      const tr = p.trend == null ? "" : `<span class="trend ${p.trend >= 0 ? "up" : "down"}">${p.trend >= 0 ? "▲" : "▼"} ${Math.abs(p.trend).toFixed(1)}</span>`;
      return `<a class="card squad-row" href="#/player/${encodeURIComponent(p.name)}">
        <div class="rating" style="background:${ratingColor(p.rating)}">${p.rating.toFixed(1)}</div>
        <div><div class="pname">${esc(p.name)}</div><div class="meta" style="text-transform:capitalize">${esc(p.pos)} · ${p.matches} apps · ${p.goals}G ${p.assists}A</div></div>
        ${tr}</a>`;
    }).join("") + `<p class="model-note">Arrow = average rating over the last 5 matches vs. before that.</p>`;
  }

  function formChart(form) {
    const W = 340, H = 150, pad = { l: 26, r: 8, t: 10, b: 20 };
    const vals = form.map((f) => f.rating);
    const lo = Math.min(5, Math.floor(Math.min(...vals))), hi = Math.max(9, Math.ceil(Math.max(...vals)));
    const x = (i) => pad.l + (form.length === 1 ? (W - pad.l - pad.r) / 2 : (i * (W - pad.l - pad.r)) / (form.length - 1));
    const y = (v) => pad.t + ((hi - v) * (H - pad.t - pad.b)) / (hi - lo);
    const grid = [];
    for (let v = lo; v <= hi; v++) grid.push(`<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${pad.l - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`);
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    const path = form.map((f, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(f.rating).toFixed(1)}`).join("");
    const dots = form.map((f, i) => `<a href="#/match/${f.match}"><circle cx="${x(i)}" cy="${y(f.rating)}" r="4.5" fill="${ratingColor(f.rating)}" stroke="var(--card)" stroke-width="1.5"><title>${fmtDate(f.ts)}: ${f.rating.toFixed(1)}</title></circle></a>`).join("");
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Match rating over time">
      ${grid.join("")}
      <line x1="${pad.l}" x2="${W - pad.r}" y1="${y(avg)}" y2="${y(avg)}" stroke="var(--secondary)" stroke-dasharray="4 3"/>
      <path d="${path}" fill="none" stroke="var(--ink)" stroke-width="1.8" opacity=".55"/>
      ${dots}
      <text x="${pad.l}" y="${H - 4}">oldest</text><text x="${W - pad.r}" y="${H - 4}" text-anchor="end">latest</text>
    </svg>
    <div class="model-note">Dashed line = average (${avg.toFixed(2)}). Tap a dot to open that match.</div>`;
  }

  async function playerView(name) {
    const p = await load(`data/players/${slug(name)}.json`);
    const a = p.averages;
    const themes = p.themes ? `
      <div class="card">
        <h3>Coach's corner</h3>
        ${p.coach ? `<p class="coach-say">${esc(p.coach.intro)}</p>` : ""}
        ${p.themes.improve.length ? `<div class="section-label">What we're working on</div>` + p.themes.improve.map((t) => `
          <div class="theme"><b>${esc(t.title)}</b><span class="tag ${t.direction}">${t.direction}</span>
            ${t.coach ? `<p class="say">${esc(t.coach)}</p>` : ""}
            <div class="model-note">Flagged in ${t.rate}% of matches (${t.recent_rate}% of the last 5)</div>
            <div class="drill-label">Coach's drill</div>
            <ul class="tips">${t.tips.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`).join("")
          : `<p class="say">Nothing keeps coming up, and that's rare. Nothing is flagged in more than 30% of your matches. Keep doing you.</p>`}
        ${p.themes.strengths.length ? `<div class="section-label">What you bring every week</div>` + p.themes.strengths.map((s) => `<div class="note good"><b>${esc(s.title)}</b><p class="say">${esc(s.coach || s.note)}</p><small>${s.rate}% of matches</small></div>`).join("") : ""}
      </div>` : `
      <div class="card">
        <h3>Coach's corner</h3>
        <p class="say">I want to see you play a few more before I start drawing conclusions. One match is a snapshot. Eight is a pattern.</p>
        <p class="model-note">Themes unlock after ${p.themes_progress.need} matches so they reflect patterns, not one-off games.</p>
        <div class="progress"><div style="width:${Math.min(100, (p.themes_progress.have / p.themes_progress.need) * 100)}%"></div></div>
        <div class="model-note">${p.themes_progress.have} of ${p.themes_progress.need} matches</div>
      </div>`;
    const impact = p.impact.map((d) => ({ ...d, count: null }));
    app.innerHTML = `
      <a class="back" href="#/squad">← Squad</a>
      <div class="profile-head">
        <div class="rating" style="background:${ratingColor(a.rating)};width:64px;height:64px;font-size:28px">${a.rating.toFixed(1)}</div>
        <div><h1>${esc(p.name)}</h1><div class="ppos"><span class="cap">${esc(p.main_pos)}</span> · ${p.matches} apps · ${p.record.W}W ${p.record.D}D ${p.record.L}L</div>
          ${p.band ? `<span class="band band-${p.band.split(" ")[0].toLowerCase()}">Average rating: ${esc(p.band.toLowerCase())} for the position</span>` : ""}</div>
      </div>
      <div class="card">
        <h3>Rating form</h3>
        ${formChart(p.form)}
      </div>
      ${themes}
      <div class="card">
        <h3>Averages</h3>
        <div class="statgrid">
          ${statCell(pct(a.pass_pct), "Pass accuracy")}
          ${statCell(a.passes_att?.toFixed(0) ?? "–", "Passes / match")}
          ${statCell(pct(a.tackle_pct), "Tackle success")}
          ${statCell(a.missed_tackles?.toFixed(1) ?? "–", "Missed tackles")}
          ${statCell(a.shots?.toFixed(1) ?? "–", "Shots / match")}
          ${p.main_pos === "goalkeeper" ? statCell(pct(a.save_pct), "Save %") : statCell(pct(a.shot_accuracy), "Shots on target")}
          ${statCell(a.key_passes?.toFixed(1) ?? "–", "Key passes / match")}
          ${statCell(pct(a.conversion), "Conversion")}
          ${statCell(p.totals.goals || 0, "Goals")}
          ${statCell(p.totals.assists || 0, "Assists")}
          ${statCell(p.totals.mom || 0, "MOTM")}
        </div>
      </div>
      <div class="card">
        <h3>What drives their rating</h3>
        <p class="model-note" style="margin-top:4px">Average effect per match.</p>
        ${driversBlock({ drivers: impact, baseline: 6.0, learned: INDEX.model[p.main_pos]?.learned, share: INDEX.model[p.main_pos]?.share })}
      </div>
      <div class="card">
        <h3>Match log</h3>
        ${[...p.form].reverse().map((f) => `<a class="log-row" href="#/match/${f.match}/${encodeURIComponent(p.name)}"><span>${fmtDate(f.ts)}</span><span class="ppos cap">${esc(f.pos)}</span><span class="r" style="color:${ratingColor(f.rating)}">${f.rating.toFixed(1)}</span></a>`).join("")}
      </div>`;
  }

  function aboutView() {
    const m = INDEX.model;
    app.innerHTML = `<div class="about">
      <h2>How it works</h2>
      <div class="card">
        <p>After every match, this site pulls the official EA Pro Clubs match report for <b>${esc(INDEX.club.name)}</b>. Only human-controlled players on our side are analysed - AI teammates and opponents are ignored.</p>
        <ul>
          <li><b>Did well / To improve</b> compares each player's passing, tackling, shooting, key passes and saves with real FC 27 benchmarks for their position (top quarter = strength, bottom quarter = flag), then reads stats in pairs: forcing passes, diving into tackles, shooting at the keeper, and rating below what the stats predict (positioning).</li>
          <li><b>Rating badge</b> places each rating against players in the same position. A 6.6 is a strong game for a keeper but a quiet one for a midfielder.</li>
          <li><b>What moved the rating</b> estimates how many rating points each action was worth, using weights measured from thousands of real FC 27 matches. "Everything else" is the part of EA's rating the match report doesn't break down (positioning, dribbles, interceptions).</li>
          <li><b>Coach's team talk</b> picks the three things the team did best and the three that most need work after every match. The same talk is texted to you within a couple of minutes of the final whistle.</li>
          <li><b>Coach's corner</b> themes appear once a player has ${INDEX.themes_min_matches}+ matches: weaknesses flagged in 30%+ of games, with whether they're improving.</li>
        </ul>
      </div>
      <div class="card">
        <h3>Rating model status</h3>
        <p class="model-note">The rating model retrains on every match we play. Each position starts on league-wide weights and shifts toward our own data as games pile up (about 25% ours after 10 matches, 50% after 30, 75% after 90).</p>
        ${Object.entries(m).map(([pos, v]) => `<div class="log-row"><span style="text-transform:capitalize">${pos}</span><span class="r">${Math.round((v.share ?? 0) * 100)}% ours · ${v.samples} matches</span></div>`).join("")}
      </div>
      <p class="model-note">Updated ${new Date(INDEX.generated).toLocaleString()}</p>
    </div>`;
  }

  // ------------------------------------------------------------ router

  async function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
    const tab = parts[0] === "squad" || parts[0] === "player" ? "squad" : parts[0] === "about" ? "about" : "matches";
    document.querySelectorAll(".tabbar a").forEach((a) => a.classList.toggle("active", a.dataset.tab === tab));
    try {
      if (parts[0] === "m") parts[0] = "match"; // short links used in texts
      if (parts[0] === "l") { // "#/l" = my latest match, "#/l/<name>" = that player's latest
        const who = parts[1] || INDEX.my_player;
        const pl = INDEX.players.find((x) => x.name === who);
        if (pl) { location.replace(`#/match/${pl.latest}/${encodeURIComponent(who)}`); return; }
        parts[0] = "";
      }
      if (parts[0] === "match" && parts[1]) await matchView(parts[1], parts[2]);
      else if (parts[0] === "player" && parts[1]) await playerView(parts[1]);
      else if (parts[0] === "squad") squadView();
      else if (parts[0] === "about") aboutView();
      else matchesView();
      if (!(parts[0] === "match" && parts[2])) window.scrollTo(0, 0);
    } catch (e) {
      app.innerHTML = `<div class="empty">Couldn't find that page.<br><a class="back" href="#/">Back to matches</a></div>`;
    }
  }

  load("data/index.json").then((idx) => {
    INDEX = idx;
    applyBrand(idx.club);
    window.addEventListener("hashchange", route);
    route();
  }).catch(() => { app.innerHTML = `<div class="empty">No data yet - the first sync hasn't run.</div>`; });
})();
