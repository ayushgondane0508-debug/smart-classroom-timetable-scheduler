import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { ArrowLeft, CalendarDays, Check, GraduationCap, Link2, MapPin, Search, Users } from "lucide-react";
import "@/scheduler.css";
import { API } from "@/client";
import DayCards from "@/DayCards";

const STORAGE_KEY = "smartclassroom.student.division";

function periodTime(start, duration, period) {
  const [h, m] = (start || "09:00").split(":").map(Number);
  const from = h * 60 + m + (period - 1) * duration;
  const fmt = minutes => `${String(Math.floor(minutes / 60) % 24).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
  return `${fmt(from)} – ${fmt(from + duration)}`;
}

function DivisionPicker({ divisions, onPick }) {
  const [query, setQuery] = useState("");
  const groups = useMemo(() => {
    const filtered = divisions.filter(item => `${item.name} ${item.department} ${item.semester}`.toLowerCase().includes(query.toLowerCase()));
    return Object.entries(filtered.reduce((acc, item) => ({ ...acc, [item.department || "Other"]: [...(acc[item.department || "Other"] || []), item] }), {}));
  }, [divisions, query]);
  return <section className="student-picker" data-testid="student-division-picker">
    <div className="portal-hero"><p className="scheduler-kicker">Student timetable</p><h1>Which division are you in?</h1><p>Pick your class once — we remember it on this phone. No login needed.</p></div>
    <div className="student-search"><Search size={16}/><input placeholder="Search division or department…" value={query} onChange={e => setQuery(e.target.value)} data-testid="student-division-search"/></div>
    {groups.length === 0 && <div className="empty-state" data-testid="student-no-divisions"><Users size={28}/><h2>No divisions found</h2><p>{divisions.length ? "Try a different search." : "The admin has not added any divisions yet."}</p></div>}
    {groups.map(([department, items], groupIndex) => <div className="student-group" key={department}><h3>{department}</h3><div className="student-division-grid">{items.map((item, index) => <motion.button key={item.id} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: (groupIndex * items.length + index) * 0.05 }} whileTap={{ scale: 0.97 }} className="student-division-card" onClick={() => onPick(item.id)} data-testid={`student-division-${item.id}`}><span className="division-badge">{item.name.slice(0, 2)}</span><div><strong>{item.name}</strong><small>{[item.semester ? `Semester ${item.semester}` : "", item.student_count ? `${item.student_count} students` : ""].filter(Boolean).join(" · ") || department}</small></div><Check size={16} className="pick-check"/></motion.button>)}</div></div>)}
  </section>;
}

function DivisionSchedule({ data, onChange }) {
  const { division, entries, timetable_name, working_days, periods_per_day, start_time, period_duration } = data;
  const [copied, setCopied] = useState(false);
  const days = working_days.length ? working_days : [...new Set(entries.map(e => e.day))];
  const periods = Array.from({ length: periods_per_day }, (_, i) => i + 1);
  const at = (day, period) => entries.find(e => e.day === day && e.period === period);
  const today = new Date().toLocaleDateString("en-US", { weekday: "long" });
  const todayCount = entries.filter(e => e.day === today).length;
  const share = async () => { const url = `${window.location.origin}/student/${division.id}`; try { await navigator.clipboard.writeText(url); } catch { window.prompt("Copy link", url); } setCopied(true); setTimeout(() => setCopied(false), 1800); };
  return <>
    <section className="portal-hero"><div className="portal-identity"><span className="portal-photo initials" data-testid="student-division-badge">{division.name.slice(0, 2)}</span><div><p className="scheduler-kicker">Student timetable · live</p><h1 data-testid="student-division-name">{division.name}</h1><p>{[division.department, division.semester ? `Semester ${division.semester}` : "", `${entries.length} sessions this week`, timetable_name].filter(Boolean).join(" · ")}</p></div></div>
      <div className="student-actions"><button className="ghost-button" onClick={onChange} data-testid="student-change-division"><ArrowLeft size={14}/> Change division</button><button className="ghost-button" onClick={share} data-testid="student-share-link">{copied ? <Check size={14}/> : <Link2 size={14}/>} {copied ? "Link copied" : "Share link"}</button>{days.includes(today) && <span className="today-pill" data-testid="student-today-pill">{todayCount ? `${todayCount} lectures today` : "No lectures today"}</span>}</div></section>
    <section className="portal-grid panel has-day-cards">
      {entries.length === 0 ? <div className="empty-state"><CalendarDays size={30}/><h2>No timetable published yet</h2><p>Your schedule appears here as soon as the admin publishes one.</p></div> : <>
        <DayCards days={days} periods={periods} cellsFor={(day, period) => entries.filter(e => e.day === day && e.period === period)} testId="student-day-cards"/>
        <div className="timetable-scroll"><table className="timetable" data-testid="student-timetable"><thead><tr><th>Period</th>{days.map(day => <th key={day}>{day}</th>)}</tr></thead><tbody>
          {periods.map(period => <tr key={period}><th>P{period}<small className="period-time">{periodTime(start_time, period_duration, period)}</small></th>{days.map(day => { const cell = at(day, period); return <td key={day}>{cell ? <div className={`timetable-cell ${cell.requires_lab ? "lab-cell" : ""}`} data-testid={`student-cell-${day}-${period}`}><strong>{cell.subject_code || cell.subject_name}</strong><span>{cell.subject_name}</span><small>{cell.teacher_name}</small><em><MapPin size={9}/> {cell.room_name}</em></div> : <span className="empty-slot">Free</span>}</td>; })}</tr>)}
        </tbody></table></div></>}
    </section>
  </>;
}

export default function StudentPortal({ divisionId }) {
  const [divisions, setDivisions] = useState(null);
  const [selected, setSelected] = useState(divisionId || window.localStorage.getItem(STORAGE_KEY) || "");
  const [state, setState] = useState({ loading: false, data: null, error: "" });
  useEffect(() => { axios.get(`${API}/public/divisions`).then(res => setDivisions(res.data)).catch(() => setDivisions([])); }, []);
  useEffect(() => {
    if (!selected) { setState({ loading: false, data: null, error: "" }); return; }
    setState({ loading: true, data: null, error: "" });
    axios.get(`${API}/public/division/${selected}`).then(res => { setState({ loading: false, data: res.data, error: "" }); window.localStorage.setItem(STORAGE_KEY, selected); window.history.replaceState(null, "", `/student/${selected}`); })
      .catch(() => { window.localStorage.removeItem(STORAGE_KEY); setSelected(""); setState({ loading: false, data: null, error: "That division no longer exists — pick another one." }); window.history.replaceState(null, "", "/student"); });
  }, [selected]);
  const change = () => { window.localStorage.removeItem(STORAGE_KEY); setSelected(""); window.history.replaceState(null, "", "/student"); };
  return <div className="teacher-portal student-portal" data-testid="student-portal">
    <div className="portal-glow"/>
    <header className="portal-header"><div className="portal-brand"><span className="scheduler-mark small">SC</span><span>Smart<strong>Classroom</strong></span></div><div className="portal-actions"><a href="/teacher-login" data-testid="student-teacher-link"><GraduationCap size={13}/> Faculty</a><a href="/" data-testid="student-home-link">← Product overview</a></div></header>
    {state.error && <div className="scheduler-error portal-inline-error" data-testid="student-error">{state.error}</div>}
    {divisions === null || state.loading ? <div className="scheduler-loading inline"><div className="scheduler-spinner"/> Loading…</div> : state.data ? <DivisionSchedule data={state.data} onChange={change}/> : <DivisionPicker divisions={divisions} onPick={setSelected}/>}
    <footer className="portal-footer">Read-only student view · updates automatically when the admin publishes a new timetable</footer>
  </div>;
}
