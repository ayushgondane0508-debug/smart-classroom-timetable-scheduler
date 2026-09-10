import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const palette = ["#2563eb", "#14b8a6", "#f59e0b", "#8b5cf6", "#ef4444", "#0ea5e9", "#84cc16", "#ec4899"];

function Tip({ active, payload, render }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tip" data-testid="chart-tooltip">{render(payload[0].payload)}</div>;
}

export function WorkloadChart({ rows }) {
  const data = rows.map(row => ({ ...row, load: row.max_per_week ? Math.round(row.lectures / row.max_per_week * 100) : null }));
  return <ResponsiveContainer width="100%" height={Math.max(220, data.length * 44)}>
    <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 6, bottom: 6 }} barCategoryGap={10}>
      <CartesianGrid horizontal={false} stroke="#eef2f7"/>
      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
      <YAxis type="category" dataKey="name" width={118} tick={{ fontSize: 11, fill: "#334155", fontWeight: 600 }} axisLine={false} tickLine={false}/>
      <Tooltip cursor={{ fill: "#eff6ff" }} content={<Tip render={row => <><strong>{row.name}</strong><span>{row.lectures} lectures / week{row.max_per_week ? ` · ${row.load}% of ${row.max_per_week} max` : ""}</span><span>{row.labs} lab sessions · busiest {row.busiest_day || "—"}</span><em>{Object.entries(row.per_day || {}).map(([day, count]) => `${day.slice(0, 3)} ${count}`).join(" · ")}</em></>}/>}/>
      <Bar dataKey="lectures" radius={[0, 8, 8, 0]} isAnimationActive animationDuration={700}>{data.map((row, index) => <Cell key={row.id} fill={row.load && row.load > 85 ? "#f59e0b" : palette[index % 2]}/>)}</Bar>
    </BarChart>
  </ResponsiveContainer>;
}

export function RoomChart({ rows }) {
  return <ResponsiveContainer width="100%" height={Math.max(220, rows.length * 44)}>
    <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 30, top: 6, bottom: 6 }} barCategoryGap={10}>
      <CartesianGrid horizontal={false} stroke="#eef2f7"/>
      <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
      <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 11, fill: "#334155", fontWeight: 600 }} axisLine={false} tickLine={false}/>
      <Tooltip cursor={{ fill: "#ecfdf5" }} content={<Tip render={row => <><strong>{row.is_lab ? "Lab" : "Room"} {row.name}</strong><span>{row.utilization}% utilised · {row.sessions} of {row.total_slots} weekly slots</span><em>Used by {row.divisions?.join(", ") || "—"}</em></>}/>}/>
      <Bar dataKey="utilization" radius={[0, 8, 8, 0]} isAnimationActive animationDuration={700}>{rows.map(row => <Cell key={row.id} fill={row.is_lab ? "#14b8a6" : "#2563eb"}/>)}</Bar>
    </BarChart>
  </ResponsiveContainer>;
}

export function SubjectDonut({ rows, total }) {
  return <div className="donut-wrap"><ResponsiveContainer width="100%" height={230}>
    <PieChart>
      <Pie data={rows} dataKey="sessions" nameKey="name" innerRadius={62} outerRadius={92} paddingAngle={3} cornerRadius={6} isAnimationActive animationDuration={800}>{rows.map((row, index) => <Cell key={row.name} fill={palette[index % palette.length]}/>)}</Pie>
      <Tooltip content={<Tip render={row => <><strong>{row.name}</strong><span>{row.sessions} sessions · {total ? Math.round(row.sessions / total * 100) : 0}% of the week</span></>}/>}/>
    </PieChart>
  </ResponsiveContainer><div className="donut-center"><strong>{total}</strong><small>sessions</small></div><div className="donut-legend">{rows.map((row, index) => <span key={row.name}><i style={{ background: palette[index % palette.length] }}/>{row.name}</span>)}</div></div>;
}

export function DensityChart({ rows }) {
  return <ResponsiveContainer width="100%" height={220}>
    <AreaChart data={rows} margin={{ left: -14, right: 12, top: 10, bottom: 0 }}>
      <defs><linearGradient id="densityFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2563eb" stopOpacity={.35}/><stop offset="100%" stopColor="#2563eb" stopOpacity={0}/></linearGradient><linearGradient id="labFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#14b8a6" stopOpacity={.4}/><stop offset="100%" stopColor="#14b8a6" stopOpacity={0}/></linearGradient></defs>
      <CartesianGrid vertical={false} stroke="#eef2f7"/>
      <XAxis dataKey="name" tickFormatter={day => day.slice(0, 3)} tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
      <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false}/>
      <Tooltip content={<Tip render={row => <><strong>{row.name}</strong><span>{row.sessions} sessions scheduled</span><em>{row.labs} in laboratories · {row.sessions - row.labs} in classrooms</em></>}/>}/>
      <Area type="monotone" dataKey="sessions" stroke="#2563eb" strokeWidth={2.5} fill="url(#densityFill)" dot={{ r: 4, fill: "#2563eb", strokeWidth: 0 }} activeDot={{ r: 6 }} isAnimationActive animationDuration={800}/>
      <Area type="monotone" dataKey="labs" stroke="#14b8a6" strokeWidth={2} fill="url(#labFill)" dot={{ r: 3, fill: "#14b8a6", strokeWidth: 0 }} isAnimationActive animationDuration={800}/>
    </AreaChart>
  </ResponsiveContainer>;
}
