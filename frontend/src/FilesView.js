import { useEffect, useRef, useState } from "react";
import { Download, FileText, FolderOpen, Trash2, UploadCloud } from "lucide-react";
import { api, errorText, fileUrl, formatBytes } from "@/client";

const categories = ["General", "Syllabus", "Notices", "Room maps", "Exam schedules"];

function UploadPanel({ onUploaded }) {
  const [form, setForm] = useState({ title: "", category: "General", file: null });
  const [state, setState] = useState({ busy: false, error: "" });
  const input = useRef(null);
  const submit = async event => {
    event.preventDefault();
    if (!form.file) { setState({ busy: false, error: "Choose a file first." }); return; }
    setState({ busy: true, error: "" });
    const body = new FormData(); body.append("file", form.file); body.append("title", form.title || form.file.name); body.append("category", form.category);
    try { await api.post("/documents", body); setForm({ title: "", category: "General", file: null }); if (input.current) input.current.value = ""; await onUploaded(); setState({ busy: false, error: "" }); }
    catch (err) { setState({ busy: false, error: errorText(err) }); }
  };
  return <form className="panel upload-panel" onSubmit={submit} data-testid="document-upload-form">
    <div className="panel-heading"><div><p className="scheduler-kicker">Cloud storage</p><h2>Upload a document</h2></div><UploadCloud size={18} className="teal-icon"/></div>
    <label className={`drop-zone ${form.file ? "has-file" : ""}`} data-testid="document-drop-zone"><input ref={input} type="file" onChange={e => setForm({ ...form, file: e.target.files?.[0] || null })} data-testid="document-file-input"/><FileText size={22}/><strong>{form.file ? form.file.name : "Choose a file"}</strong><small>{form.file ? formatBytes(form.file.size) : "PDF, Excel, images or docs · up to 15 MB"}</small></label>
    <div className="form-grid"><label>Title<input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="e.g. Semester 3 syllabus" data-testid="document-title-input"/></label><label>Category<select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} data-testid="document-category-select">{categories.map(item => <option key={item}>{item}</option>)}</select></label></div>
    {state.error && <div className="scheduler-error" data-testid="document-upload-error">{state.error}</div>}
    <button className="primary-button" disabled={state.busy} data-testid="document-upload-submit"><UploadCloud size={15}/> {state.busy ? "Uploading…" : "Upload to cloud"}</button>
  </form>;
}

function FileTable({ rows, kind, onDelete }) {
  if (!rows.length) return <div className="empty-state" data-testid={`${kind}-empty`}><FolderOpen size={28}/><h3>{kind === "documents" ? "No documents yet" : "No exports archived yet"}</h3><p>{kind === "documents" ? "Upload syllabus PDFs, notices or room maps to share them with the team." : "Every PDF or Excel export you download is archived here automatically."}</p></div>;
  return <div className="data-table-wrap"><table className="data-table" data-testid={`${kind}-table`}><thead><tr><th>File</th><th>{kind === "documents" ? "Category" : "Timetable"}</th><th>Size</th><th>Uploaded</th><th>Actions</th></tr></thead><tbody>
    {rows.map(row => <tr key={row.id} data-testid={`${kind}-row-${row.id}`}><td><div className="table-primary"><span className="table-avatar"><FileText size={15}/></span><div><strong>{row.title}</strong><small>{row.original_filename}</small></div></div></td><td>{kind === "documents" ? row.category : `${row.timetable_name} · ${row.score}/100`}</td><td>{formatBytes(row.size)}</td><td>{new Date(row.created_at).toLocaleString()}</td><td><div className="row-actions"><a className="icon-button" href={fileUrl(row.id)} target="_blank" rel="noreferrer" title="Download" data-testid={`download-${row.id}`}><Download size={14}/></a>{onDelete && <button className="icon-button danger" onClick={() => onDelete(row.id)} data-testid={`delete-document-${row.id}`}><Trash2 size={14}/></button>}</div></td></tr>)}
  </tbody></table></div>;
}

export default function FilesView() {
  const [tab, setTab] = useState("documents");
  const [docs, setDocs] = useState([]);
  const [exports, setExports] = useState([]);
  const [error, setError] = useState("");
  const load = async () => { try { const [d, e] = await Promise.all([api.get("/documents"), api.get("/exports")]); setDocs(d.data); setExports(e.data); } catch (err) { setError(errorText(err)); } };
  useEffect(() => { load(); }, []);
  const remove = async id => { if (window.confirm("Remove this document from the library?")) { await api.delete(`/documents/${id}`); await load(); } };
  return <div data-testid="files-page">
    <div className="page-intro"><div><p className="scheduler-kicker">Files & media</p><h1>Documents & export history</h1><p>Campus files and every exported timetable, stored safely in cloud object storage.</p></div><div className="segmented" role="tablist"><button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")} data-testid="files-tab-documents">Documents ({docs.length})</button><button className={tab === "exports" ? "active" : ""} onClick={() => setTab("exports")} data-testid="files-tab-exports">Export history ({exports.length})</button></div></div>
    {error && <div className="scheduler-error" data-testid="files-error">{error}</div>}
    {tab === "documents" ? <div className="files-grid"><UploadPanel onUploaded={load}/><div className="panel table-panel"><div className="table-toolbar"><strong className="toolbar-title">Document library</strong><span className="record-count">{docs.length} files</span></div><FileTable rows={docs} kind="documents" onDelete={remove}/></div></div>
      : <div className="panel table-panel"><div className="table-toolbar"><strong className="toolbar-title">Archived exports</strong><span className="record-count">{exports.length} files</span></div><FileTable rows={exports} kind="exports"/></div>}
  </div>;
}
