"use client";

import useSWR from "swr";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card, CardHeader } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { tasksApi, modelsApi, datasetsApi, type ComparisonTask, type ComparisonResult } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

export default function ComparePage() {
  const { data: tasks, isLoading, mutate } = useSWR("tasks", () => tasksApi.list());
  const { data: models } = useSWR("models", () => modelsApi.list());
  const { data: availableDatasets } = useSWR("datasets", () => datasetsApi.list());

  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    dataset_id: "eval-default",
    model_ids: [] as string[],
    metrics: ["correctness", "latency_p95", "cost_per_query"],
  });
  const [submitting, setSubmitting] = useState(false);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [report, setReport] = useState<ComparisonResult[] | null>(null);
  const [datasetCases, setDatasetCases] = useState<any[] | null>(null);
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
        metrics: form.metrics,
      } as any);
      await mutate();
      setCreating(false);
      setForm({ name: "", dataset_id: "eval-default", model_ids: [], metrics: ["correctness", "latency_p95", "cost_per_query"] });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRun(taskId: string) {
    setRunningTaskId(taskId);
    setActiveTaskProgress({});
    setTaskLogs([]);
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
        } else if (data.type === "done") {
          ws.close();
          setRunningTaskId(null);
          mutate();
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
        await mutate();
        const tasks: ComparisonTask[] = (data as any)?.data ?? [];
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
      const res = await tasksApi.report(taskId);
      setReport(res.data.results);
      setDatasetCases(res.data.dataset_cases);
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
          {t.status === "completed" && (
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

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-2">비교 모델 선택 (2개 이상)</label>
                <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
                  {models?.data.filter((m) => m.status === "active").map((m) => (
                    <label key={m.id} className="flex items-center gap-2 rounded-lg border border-gray-200 p-2 cursor-pointer hover:bg-gray-50">
                      <input
                        type="checkbox"
                        checked={form.model_ids.includes(m.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setForm({ ...form, model_ids: [...form.model_ids, m.id] });
                          } else {
                            setForm({ ...form, model_ids: form.model_ids.filter((id) => id !== m.id) });
                          }
                        }}
                      />
                      <span className="text-xs font-mono truncate">{m.id}</span>
                    </label>
                  ))}
                </div>
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
            <CardHeader title="비교 결과" subtitle={selectedTask} />
            {reportLoading ? (
              <p className="text-center text-gray-400 py-8">결과를 불러오는 중...</p>
            ) : chartData.length === 0 ? (
              <p className="text-center text-gray-400 py-8">결과 데이터가 없습니다.</p>
            ) : (
              <div className="space-y-6">
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-2">정확도 (%)</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="model" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="정확도" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50">
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">모델</th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">정확도</th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">레이턴시 P95</th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">비용 (USD)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {report?.map((r) => (
                        <tr key={r.model_id}>
                          <td className="px-4 py-2 font-mono text-xs text-blue-700">{r.model_id}</td>
                          <td className="px-4 py-2 text-right">
                            {r.metrics.correctness != null
                              ? `${(r.metrics.correctness * 100).toFixed(1)}%`
                              : "—"}
                          </td>
                          <td className="px-4 py-2 text-right">
                            {r.metrics.latency_p95 != null
                              ? `${r.metrics.latency_p95.toFixed(0)}ms`
                              : "—"}
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-xs">
                            ${r.cost_usd?.toFixed(6) ?? "0"}
                          </td>
                        </tr>
                      ))}
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
          </Card>
        )}
      </div>
    </div>
  );
}
