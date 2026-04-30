"use client";

import useSWR from "swr";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card, CardHeader } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { tasksApi, modelsApi, type ComparisonTask, type ComparisonResult } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

export default function ComparePage() {
  const { data: tasks, isLoading, mutate } = useSWR("tasks", () => tasksApi.list());
  const { data: models } = useSWR("models", () => modelsApi.list());

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
  const [reportLoading, setReportLoading] = useState(false);

  async function handleCreate() {
    if (!form.name || form.model_ids.length < 2) return;
    setSubmitting(true);
    try {
      await tasksApi.create(form);
      await mutate();
      setCreating(false);
      setForm({ name: "", dataset_id: "eval-default", model_ids: [], metrics: ["correctness", "latency_p95", "cost_per_query"] });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRun(taskId: string) {
    await tasksApi.run(taskId);
    mutate();
  }

  async function handleViewReport(taskId: string) {
    setSelectedTask(taskId);
    setReportLoading(true);
    try {
      const res = await tasksApi.report(taskId);
      setReport(res.data);
    } finally {
      setReportLoading(false);
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
        <div className="flex gap-2">
          {t.status === "pending" && (
            <Button size="sm" variant="secondary" onClick={() => handleRun(t.id)}>
              실행
            </Button>
          )}
          {t.status === "completed" && (
            <Button size="sm" variant="ghost" onClick={() => handleViewReport(t.id)}>
              결과 보기
            </Button>
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
                  <label className="block text-xs font-medium text-gray-600 mb-1">데이터셋 ID</label>
                  <input
                    type="text"
                    value={form.dataset_id}
                    onChange={(e) => setForm({ ...form, dataset_id: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  />
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
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
