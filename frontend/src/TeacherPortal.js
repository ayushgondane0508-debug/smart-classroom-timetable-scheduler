import { useEffect, useState } from "react";
import axios from "axios";
import { CalendarDays, GraduationCap, MapPin } from "lucide-react";
import "@/scheduler.css";
import { API, fileUrl } from "@/client";
import DayCards from "@/DayCards";

export function ScheduleBoard({ data, kicker = "Faculty schedule · read only", testId = "portal" }) {
  const { teacher, entries, timetable_name, working_days, periods_per_day } = data;
  const days = working_days.length ? working_days : [...new Set(entries.map(e => e.day))];
  const periods = Array.from({ length: periods_per_day }, (_, i) => i + 1);
  const at = (day, period) => entries.find(e => e.day === day && e.period === period);
  const departments = [teacher.department, ...(teacher.departments || [])].filter(Boolean).join(", ");
  return <>
    <section className="portal-hero">
      <div className="portal-identity">{teacher.photo_file_id ? <img className="portal-photo" src={fileUrl(teacher.photo_file_id)} alt={teacher.name} data-testid={`${testId}-teacher-photo`}/> : <span className="portal-photo initials" data-testid={`${testId}-teacher-initials`}>{teacher.name.split(" ").map(part => part[0]).join("").slice(0, 2)}</span>}
        <div><p className="scheduler-kicker">{kicker}</p><h1 data-testid={`${testId}-teacher-name`}>{teacher.name}</h1><p>{[departments, teacher.employee_id, `${entries.length} sessions this week`, timetable_name].filter(Boolean).join(" · ")}</p></div></div>
    </section>
    <section className="portal-grid panel has-day-cards">
      {entries.length === 0 ? <div className="empty-state"><CalendarDays size={30}/><h2>No sessions assigned yet</h2><p>Once the admin publishes a timetable, your week appears here automatically.</p></div> : <>
        <DayCards days={days} periods={periods} cellsFor={(day, period) => entries.filter(e => e.day === day && e.period === period)} testId={`${testId}-day-cards`}/>
        <div className="timetable-scroll"><table className="timetable" data-testid={`${testId}-timetable`}><thead><tr><th>Period</th>{days.map(day => <th key={day}>{day}</th>)}</tr></thead><tbody>
          {periods.map(period => <tr key={period}><th>P{period}</th>{days.map(day => { const cell = at(day, period); return <td key={day}>{cell ? <div className={`timetable-cell ${cell.requires_lab ? "lab-cell" : ""}`} data-testid={`${testId}-cell-${day}-${period}`}><strong>{cell.subject_code || cell.subject_name}</strong><span>{cell.division_name}</span><small><MapPin size={9}/> {cell.room_name}</small></div> : <span className="empty-slot">Free</span>}</td>; })}</tr>)}
        </tbody></table></div></>}
    </section>
  </>;
}

export default function TeacherPortal({ teacherId }) {
  const [state, setState] = useState({ loading: true, data: null, error: "" });
  useEffect(() => {
    axios.get(`${API}/public/teacher/${teacherId}`)
      .then(res => setState({ loading: false, data: res.data, error: "" }))
      .catch(() => setState({ loading: false, data: null, error: "We could not find this teacher's schedule. The link may be outdated." }));
  }, [teacherId]);
  if (state.loading) return <div className="scheduler-loading"><div className="scheduler-spinner"/> Loading schedule…</div>;
  if (state.error) return <div className="scheduler-loading portal-error" data-testid="portal-error"><GraduationCap size={32}/><p>{state.error}</p><a href="/" data-testid="portal-error-home-link">Back to SmartClassroom</a></div>;
  return <div className="teacher-portal" data-testid="teacher-portal">
    <div className="portal-glow"/>
    <header className="portal-header">
      <div className="portal-brand"><span className="scheduler-mark small">SC</span><span>Smart<strong>Classroom</strong></span></div>
      <div className="portal-actions"><a href="/student" data-testid="portal-student-link">Student view</a><a href="/teacher-login" data-testid="portal-signin-link">Faculty sign in</a><a href="/" data-testid="portal-home-link">← Product overview</a></div>
    </header>
    <ScheduleBoard data={state.data}/>
    <footer className="portal-footer">Live read-only view · updates automatically when the admin publishes a new timetable</footer>
  </div>;
}
