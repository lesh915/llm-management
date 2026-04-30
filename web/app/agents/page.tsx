"use client";

import useSWR from "swr";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Table } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { agentsApi, type Agent } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";

export default function AgentsPage() {
  const { data, isLoading, mutate } = useSWR("agents", () => agentsApi.list());
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", owner: "", description: "" });
  const [submitting, setSubmitting] = useState(false);

  const columns = [
    {
      key: "name",
      header: "이름",
      render: (a: Agent) => (
        <div>
          <p className="text-sm font-medium text-gray-900">{a.name}</p>
          {a.description && <p className="text-xs text-gray-400 truncate max-w-xs">{a.description}</p>}
        </div>
      ),
    },
    { key: "owner", header: "소유자" },
    {
      key: "created_at",
      header: "생성일",
      render: (a: Agent) => (
        <span className="text-xs text-gray-500">
          {formatDistanceToNow(new Date(a.created_at), { addSuffix: true, locale: ko })}
        </span>
      ),
    },
    {
      key: "id",
      header: "ID",
      render: (a: Agent) => (
        <span className="font-mono text-xs text-gray-400">{a.id.slice(0, 8)}…</span>
      ),
    },
  ];

  async function handleCreate() {
    if (!form.name || !form.owner) return;
    setSubmitting(true);
    try {
      await agentsApi.create(form);
      await mutate();
      setCreating(false);
      setForm({ name: "", owner: "", description: "" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <Header
        title="에이전트"
        subtitle={`등록된 에이전트 ${data?.meta.count ?? 0}개`}
        action={
          <Button onClick={() => setCreating(true)} size="sm">
            + 에이전트 등록
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* 생성 폼 */}
        {creating && (
          <Card>
            <h3 className="mb-4 text-base font-semibold text-gray-900">새 에이전트 등록</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">이름 *</label>
                <input
                  type="text"
                  placeholder="예: my-qa-agent"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">소유자 *</label>
                <input
                  type="text"
                  placeholder="예: team-ml"
                  value={form.owner}
                  onChange={(e) => setForm({ ...form, owner: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">설명</label>
                <textarea
                  placeholder="에이전트 설명 (선택)"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  rows={2}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>
            <div className="mt-4 flex gap-2 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setCreating(false)}>취소</Button>
              <Button size="sm" loading={submitting} onClick={handleCreate}>저장</Button>
            </div>
          </Card>
        )}

        {/* 목록 */}
        <Table
          columns={columns as never}
          data={(data?.data ?? []) as never[]}
          keyField="id"
          loading={isLoading}
          emptyMessage="등록된 에이전트가 없습니다."
        />
      </div>
    </div>
  );
}
