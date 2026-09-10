import { useEffect, useState } from "react";
import axios from "axios";
import { CalendarDays, GraduationCap, MapPin } from "lucide-react";
import "@/scheduler.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TeacherPortal({ teacherId }) {
  const [state, setState] = useState({ loading: true, data: null, error: "" });
  useEffect(() => {
    axios.get(`${API}/public/teacher/${teacherId}`)
      .then(res => setState({ loading: false, data: res.data, error: "" }))
      .catch(() => setState({ loading: false, data: null, error: "We could not find this teacher's schedule. The link may be outdated." }));
  }, [teacherId]);
  if (state.loading) return <div className="scheduler-loading"><div className="scheduler-spinner"/> Loading schedule…</div>;
  if (state.error) return <div className="scheduler-loading portal-error" data-testid="portal-error"><GraduationCap size={32}/><p>{state.error}</p><a href="/" data-testid="portal-error-home-link">Back to SmartClassroom</a></div>;
  const { teacher, entries, timetable_name, working_days, periods_per_day } = state.data;
  const days = working_days.length ? working_days : [...new Set(entries.map(e => e.day))];
  const periods = Array.from({ length: periods_per_day }, (_, i) => i + 1);
  const at = (day, period) => entries.find(e => e.day === day && e.period === period);
  return <div className="teacher-portal" data-testid="teacher-portal">
    <div className="portal-glow"/>
    <header className="portal-header">
      <div className="portal-brand"><span className="scheduler-mark small">SC</span><span>Smart<strong>Classroom</strong></span></div>
      <a href="/" data-testid="portal-home-link">← Product overview</a>
    </header>
    <section className="portal-hero">
      <p className="scheduler-kicker">Faculty schedule · read only</p>
      <h1 data-testid="portal-teacher-name">{teacher.name}</h1>
      <p>{[teacher.department, teacher.employee_id, `${entries.length} sessions this week`, timetable_name].filter(Boolean).join(" · ")}</p>
    </section>
    <section className="portal-grid panel">
      {entries.length === 0 ? <div className="empty-state"><CalendarDays size={30}/><h2>No sessions assigned yet</h2><p>Once the admin publishes a timetable, your week appears here automatically.</p></div> :
      <div className="timetable-scroll"><table className="timetable" data-testid="portal-timetable"><thead><tr><th>Period</th>{days.map(day => <th key={day}>{day}</th>)}</tr></thead><tbody>
        {periods.map(period => <tr key={period}><th>P{period}</th>{days.map(day => { const cell = at(day, period); return <td key={day}>{cell ? <div className={`timetable-cell ${cell.requires_lab ? "lab-cell" : ""}`} data-testid={`portal-cell-${day}-${period}`}><strong>{cell.subject_code || cell.subject_name}</strong><span>{cell.division_name}</span><small><MapPin size={9}/> {cell.room_name}</small></div> : <span className="empty-slot">Free</span>}</td>; })}</tr>)}
      </tbody></table></div>}
    </section>
    <footer className="portal-footer">Live read-only view · updates automatically when the admin publishes a new timetable</footer>
  </div>;
}
