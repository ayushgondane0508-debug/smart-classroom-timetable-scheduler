import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { MapPin } from "lucide-react";

export default function DayCards({ days, periods, cellsFor, onSelect, testId = "day-cards" }) {
  const [day, setDay] = useState(days[0]);
  useEffect(() => { if (!days.includes(day)) setDay(days[0]); }, [days, day]);
  if (!days.length) return null;
  const busy = periods.filter(period => cellsFor(day, period).length).length;
  return <div className="day-cards" data-testid={testId}>
    <div className="day-tabs" role="tablist">{days.map(item => <button key={item} role="tab" aria-selected={item === day} className={item === day ? "active" : ""} onClick={() => setDay(item)} data-testid={`${testId}-tab-${item.toLowerCase()}`}>{item.slice(0, 3)}{item === day && <motion.span layoutId={`${testId}-ink`} className="day-tab-ink"/>}</button>)}</div>
    <AnimatePresence mode="wait">
      <motion.div key={day} initial={{ opacity: 0, x: 18 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -18 }} transition={{ duration: 0.22 }} className="day-card-list">
        <p className="day-card-summary" data-testid={`${testId}-summary`}>{day} · {busy} of {periods.length} periods scheduled</p>
        {periods.map((period, index) => { const cells = cellsFor(day, period); return <motion.div key={period} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.045, duration: 0.3 }} className={`day-card ${cells.length ? "" : "free"}`} data-testid={`${testId}-card-${day.toLowerCase()}-${period}`}>
          <span className="day-card-period">P{period}</span>
          <div className="day-card-body">{cells.length ? cells.map(cell => <button key={cell.id} type="button" className={`day-card-session ${cell.requires_lab ? "lab" : ""}`} onClick={() => onSelect?.(cell)} data-testid={`${testId}-session-${cell.id}`}><strong>{cell.subject_code || cell.subject_name}</strong><span>{cell.subject_name}</span><small>{cell.division_name} · {cell.teacher_name}</small><em><MapPin size={9}/> {cell.room_name}</em></button>) : <span className="day-card-free">Free period</span>}</div>
        </motion.div>; })}
      </motion.div>
    </AnimatePresence>
  </div>;
}
