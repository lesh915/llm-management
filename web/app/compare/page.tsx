"use client";

import useSWR from "swr";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card, CardHeader } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { tasksApi, modelsApi, datasetsApi, artifactsApi, agentsApi, type ComparisonTask, type ComparisonResult, type AgentArtifact, type AgentTrajectory, type AgentTurn } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

function AgentTrajectoryViewer({ trajectory }: { trajectory?: AgentTrajectory }) {
  if (!trajectory || !trajectory.turns || trajectory.turns.length === 0) return (
    <div className="flex flex-col items-center justify-center py-6 bg-gray-50/50 rounded-xl border border-dashed border-gray-200">
      <span className="text-xl mb-1">🔍</span>
      <p className="text-[10px] text-gray-400 font-medium">실행 궤적이 없습니다.</p>
    </div>
  );

  return (
    <div className="mt-4 space-y-4 relative">
      {/* Vertical Line Connector */}
      <div className="absolute left-[13px] top-4 bottom-4 w-0.5 bg-gradient-to-b from-blue-200 via-indigo-100 to-transparent" />

      {trajectory.turns.map((turn, i) => (
        <div key={i} className="relative pl-8 group">
          {/* Turn Circle Marker */}
          <div className="absolute left-0 top-1 w-7 h-7 rounded-full bg-white border-2 border-blue-400 flex items-center justify-center z-10 shadow-sm group-hover:scale-110 transition-transform">
            <span className="text-[9px] font-black text-blue-600">{i + 1}</span>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm hover:shadow-lg transition-all duration-300 hover:border-blue-100">
            <div className="flex items-center justify-between mb-3 border-b border-gray-50 pb-2">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full text-[9px] font-bold uppercase tracking-wider border border-blue-100">
                  TURN {turn.turn_index + 1}
                </span>
                {turn.response && <span className="px-2 py-0.5 bg-green-50 text-green-600 rounded-full text-[9px] font-bold uppercase tracking-wider border border-green-100">FINAL</span>}
              </div>
              {turn.metrics && (
                <div className="flex gap-3 text-[9px] text-gray-400 font-mono bg-gray-50 px-2 py-1 rounded-md">
                  <span className="flex items-center gap-1">⏱️ {(turn.metrics as any).latency_ms?.toFixed(0)}ms</span>
                  <span className="flex items-center gap-1">🪙 {(turn.metrics as any).input_tokens + (turn.metrics as any).output_tokens} tokens</span>
                  {(turn.metrics as any).cumulative_tokens && (
                    <span className="flex items-center gap-1 ml-2 pl-2 border-l border-gray-200">
                      📊 Cumulative: <span className="text-blue-600">{(turn.metrics as any).cumulative_tokens.toLocaleString()}</span>
                    </span>
                  )}
                </div>
              )}
            </div>
            
            <div className="space-y-4">
              {turn.thought && (
                <div className="relative">
                  <span className="text-[9px] font-bold text-indigo-400 uppercase flex items-center gap-1 mb-1.5 tracking-tight">
                    <span className="text-xs">🧠</span> Reasoning
                  </span>
                  <p className="text-[11px] text-indigo-900 italic leading-relaxed bg-indigo-50/20 p-3 rounded-xl border border-indigo-100/50 backdrop-blur-sm">
                    {turn.thought}
                  </p>
                </div>
              )}
              
              {turn.action && (
                <div className="bg-gradient-to-br from-amber-50 to-orange-50/30 p-3 rounded-xl border border-amber-100/50 shadow-inner">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[9px] font-bold text-amber-600 uppercase flex items-center gap-1 tracking-tight">
                      <span className="text-xs">🛠️</span> Tool Call: {String(turn.action.name)}
                    </span>
                    <span className="text-[8px] font-mono text-amber-400 bg-white px-1.5 py-0.5 rounded border border-amber-50">ID: {String(turn.action.id).slice(0, 8)}...</span>
                  </div>
                  <div className="font-mono text-[10px] text-amber-900 bg-white/60 p-2.5 rounded-lg border border-amber-50/50 break-all overflow-x-auto max-h-32 scrollbar-thin">
                    <pre className="whitespace-pre-wrap">{JSON.stringify(turn.action.input || turn.action.arguments, null, 2)}</pre>
                  </div>
                </div>
              )}
              
              {turn.observation && (
                <div className="bg-gradient-to-br from-emerald-50 to-teal-50/30 p-3 rounded-xl border border-emerald-100/50 shadow-inner">
                  <span className="text-[9px] font-bold text-emerald-600 uppercase flex items-center gap-1 mb-2 tracking-tight">
                    <span className="text-xs">📡</span> Environment Feedback
                  </span>
                  <div className="text-[11px] text-emerald-900 bg-white/60 p-3 rounded-xl border border-emerald-50/50 leading-relaxed font-mono">
                    {turn.observation}
                  </div>
                </div>
              )}

              {/* State Change Highlights */}
              {turn.state_snapshot && Object.keys(turn.state_snapshot).length > 0 && (
                <div className="pt-2 border-t border-gray-50 flex flex-wrap gap-1.5">
                  <span className="text-[9px] font-bold text-gray-400 uppercase w-full mb-1">State Updated</span>
                  {Object.entries(turn.state_snapshot).map(([key, val]) => (
                    <div key={key} className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-[9px] flex items-center gap-1.5 border border-gray-200">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                      <span className="font-bold">{key}:</span>
                      <span className="truncate max-w-[80px] italic">{String(val)}</span>
                    </div>
                  ))}
                </div>
              )}
              
              {turn.response && (
                <div className="mt-2 pt-4 border-t-2 border-dashed border-blue-50">
                  <span className="text-[9px] font-black text-blue-600 uppercase flex items-center gap-1 mb-2 tracking-widest">
                    <span className="text-sm">✨</span> Final Agent Output
                  </span>
                  <div className="text-[12px] text-gray-800 font-medium leading-relaxed bg-gradient-to-br from-blue-50 to-white p-4 rounded-2xl border-2 border-blue-100 shadow-sm">
                    {turn.response}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function ComparePage() {
  const { data: tasks, isLoading, mutate } = useSWR("tasks", () => tasksApi.list());
  const { data: models } = useSWR("models", () => modelsApi.list());
  const { data: availableDatasets } = useSWR("datasets", () => datasetsApi.list());
  const { data: agents } = useSWR("agents", () => agentsApi.list());

  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    dataset_id: "eval-default",
    model_ids: [] as string[],
    agent_id: "",
    artifact_id: "",
    baseline_model_id: ""
  });
  const [selectedAgentArtifacts, setSelectedAgentArtifacts] = useState<AgentArtifact[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [report, setReport] = useState<ComparisonResult[] | null>(null);
  const [datasetCases, setDatasetCases] = useState<any[] | null>(null);
  const [artifact, setArtifact] = useState<AgentArtifact | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [activeTaskProgress, setActiveTaskProgress] = useState<{ [model: string]: { done: number, total: number, pct: number, latency_ms: number, case_id?: string, message?: string } }>({});
  const [taskLogs, setTaskLogs] = useState<{ time: string, model: string, msg: string }[]>([]);
  const [runningTaskId, setRunningTaskId] = useState<string | null>(null);

  async function handleCreate() {
    if (!form.name || form.model_ids.length < 2) return;
    setSubmitting(true);
    try {
      await tasksApi.create({
        name: form.name,
        dataset_id: form.dataset_id,
        models: form.model_ids,
        artifact_id: form.artifact_id || undefined,
        baseline_model_id: form.baseline_model_id || undefined,
      });
      await mutate();
      setCreating(false);
      setForm({ name: "", dataset_id: "eval-default", model_ids: [], agent_id: "", artifact_id: "", baseline_model_id: "" });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRun(taskId: string) {
    setRunningTaskId(taskId);
    setActiveTaskProgress({});
    setTaskLogs([]);
    setSelectedTask(null);
    setReport(null);
    mutate();

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/api/ws/tasks/${taskId}/progress`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);

        // Server signals Redis subscription is open → NOW safe to start task
        if (data.type === "ready") {
          console.log("WS ready, starting task...");
          try {
            await tasksApi.run(taskId);
            mutate();
          } catch (err) {
            console.error("Failed to run task", err);
            setRunningTaskId(null);
            ws.close();
            alert("태스크 시작에 실패했습니다.");
          }
        } else if (data.type === "done" || data.type === "task_done" || data.type === "task_failed") {
          ws.close();
          setRunningTaskId(null);
          await mutate();
          // Auto view report on completion
          handleViewReport(taskId);
        } else if (data.model_id) {
          setActiveTaskProgress(prev => ({ ...prev, [data.model_id]: data }));
          if (data.message) {
            setTaskLogs(prev => [{
              time: new Date().toLocaleTimeString(),
              model: data.model_id.split('/').pop() || data.model_id,
              msg: `Processing ${data.case_id}: ${data.message}`
            }, ...prev].slice(0, 10));
          }
        }
      } catch (e) {
        console.error("WS parse error", e);
      }
    };

    ws.onopen = () => {
      console.log("WS connection opened, waiting for ready signal...");
    };

    ws.onclose = () => {
      // If task is still running (WS dropped mid-run), poll until it completes
      const pollId = setInterval(async () => {
        const fresh = await mutate();
        const tasks: ComparisonTask[] = (fresh as any)?.data ?? [];
        const current = tasks.find((t: ComparisonTask) => t.id === taskId);
        if (!current || current.status !== "running") {
          clearInterval(pollId);
          setRunningTaskId(null);
        }
      }, 3000);
      // Also clear after 10 minutes (safety net)
      setTimeout(() => { clearInterval(pollId); setRunningTaskId(null); }, 600000);
    };

    ws.onerror = (e) => {
      console.error("WS error", e);
      setRunningTaskId(null);
    };
  }

  async function handleViewReport(taskId: string) {
    setSelectedTask(taskId);
    setReportLoading(true);
    try {
      console.log("Fetching report for task:", taskId);
      const res = await tasksApi.report(taskId);
      setReport(res.data.results);
      setDatasetCases(res.data.dataset_cases);
      
      // Fetch task details to get artifact_id
      const taskRes = await tasksApi.get(taskId);
      const task = taskRes.data;
      console.log("Task details fetched:", task);
      
      if (task?.artifact_id) {
        console.log("Fetching artifact content for ID:", task.artifact_id);
        try {
          const art = await artifactsApi.get(task.artifact_id);
          console.log("Artifact fetched:", art.data);
          setArtifact(art.data);
        } catch (e) {
          console.error("Failed to fetch artifact", e);
          setArtifact(null);
        }
      } else {
        console.log("No artifact_id found for this task.");
        setArtifact(null);
      }
    } finally {
      setReportLoading(false);
    }
  }

  async function handleDelete(taskId: string) {
    if (!confirm("정말 이 분석을 삭제하시겠습니까?")) return;
    try {
      await tasksApi.delete(taskId);
      mutate();
      if (selectedTask === taskId) {
        setSelectedTask(null);
        setReport(null);
      }
    } catch (err) {
      alert("삭제 중 오류가 발생했습니다.");
    }
  }

  const taskColumns = [
    {
      key: "name",
      header: "태스크명",
      render: (t: ComparisonTask) => (
        <span className="text-sm font-medium text-gray-900">{t.name}</span>
      ),
    },
    {
      key: "model_ids",
      header: "모델",
      render: (t: ComparisonTask) => (
        <span className="text-xs text-gray-500">{t.model_ids.length}개 모델</span>
      ),
    },
    {
      key: "status",
      header: "상태",
      render: (t: ComparisonTask) => <StatusBadge status={t.status} />,
    },
    {
      key: "created_at",
      header: "생성일",
      render: (t: ComparisonTask) => (
        <span className="text-xs text-gray-400">
          {formatDistanceToNow(new Date(t.created_at), { addSuffix: true, locale: ko })}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (t: ComparisonTask) => (
        <div className="flex gap-2 items-center">
          {/* 실행/재실행 버튼 */}
          <Button 
            size="sm" 
            variant="secondary" 
            onClick={() => handleRun(t.id)}
            disabled={runningTaskId === t.id}
          >
            {t.status === "pending" ? "실행" : "재실행"}
          </Button>

          {/* 결과 보기 버튼 */}
          {(t.status === "completed" || t.status === "failed") && (
            <Button size="sm" variant="ghost" onClick={() => handleViewReport(t.id)}>
              결과 보기
            </Button>
          )}

          {/* 삭제 버튼 */}
          <Button 
            size="sm" 
            variant="ghost" 
            className="text-red-600" 
            onClick={() => handleDelete(t.id)}
          >
            삭제
          </Button>

          {/* 상태 표시 */}
          {(t.status === "running" || runningTaskId === t.id) && (
            <div className="text-[10px] text-blue-600 font-bold px-2 animate-pulse">
              RUNNING
            </div>
          )}
        </div>
      ),
    },
  ];

  // 차트 데이터 변환
  const chartData = report?.map((r) => ({
    model: r.model_id.split("/").pop() ?? r.model_id,
    정확도: r.metrics.correctness != null ? Math.round(r.metrics.correctness * 100) : 0,
    레이턴시: r.metrics.latency_p95 != null ? Math.round(r.metrics.latency_p95) : 0,
    비용: r.cost_usd != null ? parseFloat(r.cost_usd.toFixed(4)) : 0,
  })) ?? [];

  return (
    <div className="flex flex-col h-full">
      <Header
        title="비교 분석"
        subtitle="다중 모델 성능 비교"
        action={<Button size="sm" onClick={() => setCreating(true)}>+ 비교 태스크 생성</Button>}
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* 생성 폼 */}
        {creating && (
          <Card>
            <h3 className="mb-4 text-base font-semibold">새 비교 태스크</h3>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">태스크명 *</label>
                  <input
                    type="text"
                    placeholder="예: Claude vs GPT-4 Benchmark"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">데이터셋 선택</label>
                  <select
                    value={form.dataset_id}
                    onChange={(e) => setForm({ ...form, dataset_id: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  >
                    <option value="eval-default">기본값 (개발용 스텁)</option>
                    {availableDatasets?.data.map((d: any) => (
                      <option key={d.id} value={d.id}>{d.id}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">에이전트 선택 (선택 사항)</label>
                  <select
                    value={form.agent_id}
                    onChange={async (e) => {
                      const agentId = e.target.value;
                      setForm({ ...form, agent_id: agentId, artifact_id: "" });
                      if (agentId) {
                        const res = await agentsApi.listArtifacts(agentId);
                        setSelectedAgentArtifacts(res.data);
                      } else {
                        setSelectedAgentArtifacts([]);
                      }
                    }}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  >
                    <option value="">선택 안 함 (범용 비교)</option>
                    {agents?.data.map((a: any) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">기존 프롬프트(Artifact) 선택</label>
                  <select
                    value={form.artifact_id}
                    onChange={(e) => setForm({ ...form, artifact_id: e.target.value })}
                    disabled={!form.agent_id}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-gray-50 disabled:text-gray-400"
                  >
                    <option value="">프롬프트 선택</option>
                    {selectedAgentArtifacts.map((art) => (
                      <option key={art.id} value={art.id}>{art.type} (v{art.version})</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-2">비교 모델 선택 (2개 이상)</label>
                <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto mb-4">
                  {models?.data.filter((m) => m.status === "active").map((m) => (
                    <label key={m.id} className="flex items-center gap-2 rounded-lg border border-gray-200 p-2 cursor-pointer hover:bg-gray-50">
                      <input
                        type="checkbox"
                        checked={form.model_ids.includes(m.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setForm({ ...form, model_ids: [...form.model_ids, m.id] });
                          } else {
                            const newModelIds = form.model_ids.filter((id) => id !== m.id);
                            setForm({ 
                              ...form, 
                              model_ids: newModelIds,
                              baseline_model_id: form.baseline_model_id === m.id ? "" : form.baseline_model_id
                            });
                          }
                        }}
                      />
                      <span className="text-xs font-mono truncate">{m.id}</span>
                    </label>
                  ))}
                </div>

                {form.model_ids.length > 0 && (
                  <div className="p-3 bg-blue-50 rounded-xl border border-blue-100">
                    <label className="block text-[10px] font-bold text-blue-600 mb-1 uppercase tracking-wider">기준 모델 설정 (기존 에이전트 사용 모델)</label>
                    <select
                      value={form.baseline_model_id}
                      onChange={(e) => setForm({ ...form, baseline_model_id: e.target.value })}
                      className="w-full rounded-lg border border-blue-200 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    >
                      <option value="">기준 모델 선택 (Delta 분석용)</option>
                      {form.model_ids.map(id => (
                        <option key={id} value={id}>{id}</option>
                      ))}
                    </select>
                    <p className="mt-1 text-[10px] text-blue-400">선택한 모델을 기준으로 다른 모델들의 성능 변화(가, 나, 다)를 추적합니다.</p>
                  </div>
                )}
              </div>
            </div>
            <div className="mt-4 flex gap-2 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setCreating(false)}>취소</Button>
              <Button
                size="sm"
                loading={submitting}
                onClick={handleCreate}
                disabled={!form.name || form.model_ids.length < 2}
              >
                생성
              </Button>
            </div>
          </Card>
        )}

        {/* 태스크 목록 */}
        <Table
          columns={taskColumns as never}
          data={(tasks?.data ?? []) as never[]}
          keyField="id"
          loading={isLoading}
          emptyMessage="생성된 비교 태스크가 없습니다."
        />

        {/* 프로그레스 영역 */}
        {runningTaskId && (
          <Card>
            <CardHeader title="실시간 진행 상태" subtitle={`태스크 실행 중 (ID: ${runningTaskId})`} />
            <div className="space-y-4 p-4">
              {Object.keys(activeTaskProgress).length === 0 ? (
                <div className="text-center py-4">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto mb-2"></div>
                  <p className="text-xs text-gray-500">분석을 시작하는 중입니다...</p>
                </div>
              ) : (
                Object.entries(activeTaskProgress).map(([model, p]) => {
                  const percent = p.total > 0 ? (p.done / p.total) * 100 : 0;
                  return (
                    <div key={model}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-mono font-medium text-gray-700">{model}</span>
                        <span className="text-gray-500">
                          {p.done} / {p.total} 완료 (최근 Latency: {(p.latency_ms / 1000).toFixed(1)}s)
                        </span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${Math.max(5, percent)}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
              
              {/* 라이브 로그 */}
              <div className="mt-4 pt-4 border-t border-gray-100">
                <p className="text-[10px] font-bold text-gray-400 uppercase mb-2">실시간 로그 (Live Logs)</p>
                <div className="bg-gray-900 rounded-lg p-3 font-mono text-[10px] space-y-1 h-32 overflow-y-auto">
                  {taskLogs.length === 0 ? (
                    <p className="text-gray-600 italic">대기 중...</p>
                  ) : (
                    taskLogs.map((log, i) => (
                      <div key={i} className="flex gap-2">
                        <span className="text-gray-500">[{log.time}]</span>
                        <span className="text-blue-400 font-bold">[{log.model}]</span>
                        <span className="text-gray-300">{log.msg}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* 결과 차트 */}
        {selectedTask && (
          <Card>
            <CardHeader 
              title="비교 결과" 
              subtitle={tasks?.data.find(t => t.id === selectedTask)?.name || selectedTask} 
            />
            {reportLoading ? (
              <p className="text-center text-gray-400 py-8">결과를 불러오는 중...</p>
            ) : (
              <>
                {/* 에러 메시지 표시 */}
                {(() => {
                  const t = tasks?.data.find(t => t.id === selectedTask);
                  if (t?.status === "failed" && t.error_message) {
                    return (
                      <div className="mx-6 mt-2 mb-4 p-4 bg-red-50 border border-red-100 rounded-xl">
                        <div className="flex items-center gap-2 text-red-700 font-bold text-xs mb-1">
                          <span className="text-lg">⚠️</span> 분석 중 오류가 발생했습니다
                        </div>
                        <p className="text-xs text-red-600 bg-white/50 p-2 rounded border border-red-50 font-mono whitespace-pre-wrap">
                          {t.error_message}
                        </p>
                      </div>
                    );
                  }
                  return null;
                })()}

                {chartData.length === 0 ? (
                  <p className="text-center text-gray-400 py-8">결과 데이터가 없습니다.</p>
                ) : (
                  <div className="space-y-6">
                
                {/* 기존 프롬프트 표시 영역 */}
                {artifact && (
                  <div className="mx-6 p-4 bg-blue-50/50 border border-blue-100 rounded-xl">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="p-1 bg-blue-500 rounded text-white text-[10px] font-bold">ORIGINAL PROMPT</span>
                        <h4 className="text-sm font-bold text-gray-900">에이전트에서 동작 중인 기존 프롬프트</h4>
                      </div>
                      <span className="text-[10px] text-blue-400 font-mono">v{artifact.version}</span>
                    </div>
                    <div className="space-y-3">
                      {(artifact.content as any).system && (
                        <div>
                          <span className="block text-[9px] font-bold text-blue-400 uppercase mb-1">System Prompt</span>
                          <div className="bg-white p-3 rounded-lg border border-blue-50 text-xs text-gray-700 whitespace-pre-wrap leading-relaxed shadow-sm">
                            {(artifact.content as any).system}
                          </div>
                        </div>
                      )}
                      {(artifact.content as any).template && (
                        <div>
                          <span className="block text-[9px] font-bold text-blue-400 uppercase mb-1">User Template</span>
                          <div className="bg-white p-3 rounded-lg border border-blue-50 text-xs text-gray-700 whitespace-pre-wrap leading-relaxed shadow-sm">
                            {(artifact.content as any).template}
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="mt-3 pt-3 border-t border-blue-100 flex items-center gap-2 text-[10px] text-blue-500">
                      <span className="font-bold">목표:</span>
                      <span>모델 변경 시 위 프롬프트의 의도와 성능이 유지되는지 분석합니다.</span>
                    </div>
                  </div>
                )}

                {/* Agent Performance Summary Cards */}
                {(() => {
                  if (!report || report.length === 0) return null;
                  
                  const avgReasoning = Math.round(report.reduce((acc, r) => acc + (r.metrics.reasoning_volume || 0), 0) / report.length);
                  const avgToolRate = Math.round((report.reduce((acc, r) => acc + (r.metrics.tool_usage_rate || 0), 0) / report.length) * 100);
                  const avgTurns = (report.reduce((acc, r) => acc + (r.metrics.avg_turns || 0), 0) / report.length).toFixed(1);
                  const totalSessions = report.reduce((acc, r) => acc + (r.trajectories?.length || 0), 0);

                  return (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mx-6 mb-6">
                      <div className="bg-gradient-to-br from-indigo-500 to-blue-600 p-5 rounded-3xl text-white shadow-xl shadow-blue-200 hover:scale-[1.02] transition-transform cursor-default">
                        <div className="flex items-center gap-2 mb-2 opacity-80">
                          <span className="text-sm">🧠</span>
                          <span className="text-[10px] font-bold uppercase tracking-widest">Avg Reasoning Depth</span>
                        </div>
                        <div className="flex items-baseline gap-1">
                          <span className="text-3xl font-black">{avgReasoning}</span>
                          <span className="text-xs opacity-70">chars/turn</span>
                        </div>
                        <div className="mt-2 w-full bg-white/20 h-1 rounded-full overflow-hidden">
                          <div className="bg-white h-full" style={{ width: '65%' }} />
                        </div>
                      </div>

                      <div className="bg-gradient-to-br from-emerald-500 to-teal-600 p-5 rounded-3xl text-white shadow-xl shadow-emerald-200 hover:scale-[1.02] transition-transform cursor-default">
                        <div className="flex items-center gap-2 mb-2 opacity-80">
                          <span className="text-sm">🛠️</span>
                          <span className="text-[10px] font-bold uppercase tracking-widest">Tool Success Rate</span>
                        </div>
                        <div className="flex items-baseline gap-1">
                          <span className="text-3xl font-black">{avgToolRate}%</span>
                          <span className="text-xs opacity-70">avg</span>
                        </div>
                        <div className="mt-2 w-full bg-white/20 h-1 rounded-full overflow-hidden">
                          <div className="bg-white h-full" style={{ width: '82%' }} />
                        </div>
                      </div>

                      <div className="bg-gradient-to-br from-amber-500 to-orange-600 p-5 rounded-3xl text-white shadow-xl shadow-amber-200 hover:scale-[1.02] transition-transform cursor-default">
                        <div className="flex items-center gap-2 mb-2 opacity-80">
                          <span className="text-sm">🔄</span>
                          <span className="text-[10px] font-bold uppercase tracking-widest">Mean Turn Count</span>
                        </div>
                        <div className="flex items-baseline gap-1">
                          <span className="text-3xl font-black">{avgTurns}</span>
                          <span className="text-xs opacity-70">turns</span>
                        </div>
                        <div className="mt-2 w-full bg-white/20 h-1 rounded-full overflow-hidden">
                          <div className="bg-white h-full" style={{ width: '45%' }} />
                        </div>
                      </div>

                      <div className="bg-gradient-to-br from-gray-700 to-gray-900 p-5 rounded-3xl text-white shadow-xl shadow-gray-200 hover:scale-[1.02] transition-transform cursor-default">
                        <div className="flex items-center gap-2 mb-2 opacity-80">
                          <span className="text-sm">💾</span>
                          <span className="text-[10px] font-bold uppercase tracking-widest">Total Memory Traces</span>
                        </div>
                        <div className="flex items-baseline gap-1">
                          <span className="text-3xl font-black">{totalSessions}</span>
                          <span className="text-xs opacity-70">sessions</span>
                        </div>
                        <div className="mt-2 w-full bg-white/20 h-1 rounded-full overflow-hidden">
                          <div className="bg-white h-full" style={{ width: '100%' }} />
                        </div>
                      </div>
                    </div>
                  );
                })()}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 px-6 mb-8">
                  <div className="bg-white p-4 rounded-2xl border border-gray-100 shadow-sm">
                    <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-4">정확도 (%)</p>
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="model" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                        <Tooltip 
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                          labelStyle={{ fontWeight: 'bold', fontSize: '12px' }}
                        />
                        <Bar dataKey="정확도" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={30} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="bg-white p-4 rounded-2xl border border-gray-100 shadow-sm">
                    <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-4">레이턴시 (ms)</p>
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="model" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                        <Tooltip 
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                          labelStyle={{ fontWeight: 'bold', fontSize: '12px' }}
                        />
                        <Bar dataKey="레이턴시" fill="#f59e0b" radius={[4, 4, 0, 0]} barSize={30} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="bg-white p-4 rounded-2xl border border-gray-100 shadow-sm">
                    <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-4">추정 비용 (USD)</p>
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="model" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                        <Tooltip 
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                          labelStyle={{ fontWeight: 'bold', fontSize: '12px' }}
                        />
                        <Bar dataKey="비용" fill="#10b981" radius={[4, 4, 0, 0]} barSize={30} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50/50">
                        <th className="px-4 py-3 text-left text-[10px] font-black text-gray-400 uppercase tracking-wider">모델</th>
                        <th className="px-4 py-3 text-right text-[10px] font-black text-gray-400 uppercase tracking-wider">정확도</th>
                        <th className="px-4 py-3 text-right text-[10px] font-black text-gray-400 uppercase tracking-wider">레이턴시</th>
                        <th className="px-4 py-3 text-right text-[10px] font-black text-gray-400 uppercase tracking-wider">평균 턴수</th>
                        <th className="px-4 py-3 text-right text-[10px] font-black text-gray-400 uppercase tracking-wider">도구 활용률</th>
                        <th className="px-4 py-3 text-right text-[10px] font-black text-gray-400 uppercase tracking-wider">비용 (USD)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {(() => {
                        const baseline = report?.find(r => r.model_id === tasks?.data.find(t => t.id === selectedTask)?.baseline_model_id);
                        
                        return report?.map((r) => {
                          const isBaseline = r.model_id === baseline?.model_id;
                          
                          const getDelta = (val: number | undefined, baseVal: number | undefined, higherBetter = true) => {
                            if (val == null || baseVal == null || isBaseline) return null;
                            const diff = val - baseVal;
                            const percent = (diff / baseVal) * 100;
                            const improved = higherBetter ? diff > 0 : diff < 0;
                            return (
                              <span className={`ml-1.5 text-[9px] font-bold ${improved ? 'text-green-500' : 'text-red-500'}`}>
                                {diff > 0 ? '+' : ''}{percent.toFixed(1)}%
                              </span>
                            );
                          };

                          return (
                            <tr key={r.model_id} className={`hover:bg-gray-50/30 ${isBaseline ? 'bg-blue-50/30' : ''}`}>
                              <td className="px-4 py-3">
                                <div className="flex flex-col">
                                  <span className="font-mono text-xs text-blue-700 font-bold">{r.model_id}</span>
                                  {isBaseline && (
                                    <span className="mt-0.5 text-[8px] font-black bg-blue-500 text-white px-1 py-0.5 rounded w-fit uppercase tracking-tighter">Existing / Baseline</span>
                                  )}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex items-center justify-end">
                                  <span className="font-bold text-gray-900">{r.metrics.correctness != null ? (r.metrics.correctness * 100).toFixed(1) + '%' : '—'}</span>
                                  {getDelta(r.metrics.correctness, baseline?.metrics.correctness, true)}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex items-center justify-end">
                                  <span className="text-gray-600">{r.metrics.latency_p95 != null ? r.metrics.latency_p95.toFixed(0) + 'ms' : '—'}</span>
                                  {getDelta(r.metrics.latency_p95, baseline?.metrics.latency_p95, false)}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex items-center justify-end">
                                  <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-[10px] font-bold">{r.metrics.avg_turns?.toFixed(1) ?? '—'} turns</span>
                                  {getDelta(r.metrics.avg_turns, baseline?.metrics.avg_turns, false)}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="flex items-center justify-end">
                                  <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded text-[10px] font-bold">{(r.metrics.tool_usage_rate || 0 * 100).toFixed(0)}% used</span>
                                  {getDelta(r.metrics.tool_usage_rate, baseline?.metrics.tool_usage_rate, true)}
                                </div>
                              </td>
                              <td className="px-4 py-3 text-right font-mono text-xs text-gray-400">
                                ${r.cost_usd?.toFixed(6) ?? "0"}
                              </td>
                            </tr>
                          );
                        });
                      })()}
                    </tbody>
                  </table>
                </div>

                {/* 상세 평가 내역 내역 */}
                {datasetCases && (
                  <div className="pt-6 border-t border-gray-100">
                    <h4 className="text-sm font-bold text-gray-900 mb-4">상세 평가 내역 (Transparency Log)</h4>
                    <div className="space-y-4">
                      {datasetCases.map((caseItem, caseIdx) => (
                        <div key={caseItem.id} className="rounded-xl border border-gray-100 bg-gray-50/50 p-4">
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-[10px] font-black text-gray-400 tracking-widest uppercase">CASE {caseIdx + 1}</span>
                            <div className="px-2 py-0.5 bg-white border border-gray-200 rounded text-[10px] font-mono text-gray-500">ID: {caseItem.id}</div>
                          </div>
                          
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            <div className="bg-white p-3 rounded-lg border border-gray-100">
                              <span className="block text-[10px] font-bold text-blue-500 mb-1 uppercase">Prompt</span>
                              <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">{caseItem.input?.[0]?.content || "No input"}</p>
                            </div>
                            <div className="bg-white p-3 rounded-lg border border-gray-100">
                              <span className="block text-[10px] font-bold text-green-600 mb-1 uppercase">Expected Output</span>
                              <p className="text-xs text-gray-700 leading-relaxed font-medium">{caseItem.expected || "(None)"}</p>
                            </div>
                          </div>

                          <div className="space-y-2">
                            <span className="block text-[10px] font-bold text-gray-400 mb-1 uppercase">Model Responses</span>
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                              {report?.map(r => {
                                const output = r.raw_outputs?.find(o => o.case_id === caseItem.id);
                                const isCorrect = output?.content?.toString().toLowerCase().includes(caseItem.expected?.toLowerCase());
                                return (
                                  <div key={r.model_id} className="bg-white p-2.5 rounded-lg border border-gray-100 shadow-sm">
                                    <div className="flex justify-between items-start mb-1.5">
                                      <span className="text-[10px] font-mono font-bold text-gray-900 truncate max-w-[120px]">{r.model_id.split('/').pop()}</span>
                                      {output?.error ? (
                                        <span className="text-[9px] font-bold text-red-500">FAILED</span>
                                      ) : isCorrect ? (
                                        <span className="text-[9px] font-bold text-green-500">CORRECT</span>
                                      ) : (
                                        <span className="text-[9px] font-bold text-orange-400">MISMATCH</span>
                                      )}
                                    </div>
                                    <div className="text-[11px] text-gray-600 line-clamp-3 bg-gray-50 p-1.5 rounded italic">
                                      {output?.error || output?.content || "No response"}
                                    </div>
                                    
                                    {/* 에이전트 트래젝토리 보기 */}
                                    {r.trajectories && r.trajectories.find(t => t.case_id === caseItem.id) && (
                                      <div className="mt-4 pt-4 border-t border-gray-100">
                                        <h6 className="text-[10px] font-black text-blue-500 uppercase mb-3 flex items-center gap-2">
                                          <span className="p-1 bg-blue-500 rounded-full text-[8px] text-white">★</span>
                                          Execution Trajectory Comparison
                                        </h6>
                                        <AgentTrajectoryViewer 
                                          trajectory={r.trajectories.find(t => t.case_id === caseItem.id)} 
                                        />
                                      </div>
                                    )}

                                    <div className="mt-1.5 text-[9px] text-gray-400 text-right">
                                      {output?.latency_ms?.toFixed(0)}ms
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </Card>
    )}
      </div>
    </div>
  );
}
