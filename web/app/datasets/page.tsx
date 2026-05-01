"use client";

import useSWR from "swr";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { datasetsApi } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";

export default function DatasetsPage() {
  const { data: datasets, isLoading, mutate } = useSWR("datasets", () => datasetsApi.list());
  const [creating, setCreating] = useState(false);
  const [newId, setNewId] = useState("");
  const [cases, setCases] = useState([{ id: "case-1", input: "", expected: "" }]);
  const [submitting, setSubmitting] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<any | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editCases, setEditCases] = useState<any[]>([]);

  async function handleView(id: string) {
    setLoadingDetails(true);
    setIsEditing(false);
    try {
      const res = await datasetsApi.get(id);
      const data = { id, ...res.data };
      setSelectedDataset(data);
      setEditCases(data.cases.map((c: any) => ({
        id: c.id,
        input: c.input_messages?.[0]?.content || c.input || "",
        expected: c.expected_output || c.expected || ""
      })));
    } finally {
      setLoadingDetails(false);
    }
  }

  async function handleEditSave() {
    if (!selectedDataset || editCases.some(c => !c.input)) return;
    setSubmitting(true);
    try {
      const formattedCases = editCases.map(c => ({
        id: c.id,
        input_messages: [{ role: "user", content: c.input }],
        expected_output: c.expected
      }));
      await datasetsApi.create({ id: selectedDataset.id, cases: formattedCases });
      await mutate();
      setIsEditing(false);
      handleView(selectedDataset.id); // Refresh view
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreate() {
    if (!newId || cases.some(c => !c.input)) return;
    setSubmitting(true);
    try {
      const formattedCases = cases.map(c => ({
        id: c.id,
        input_messages: [{ role: "user", content: c.input }],
        expected_output: c.expected
      }));
      await datasetsApi.create({ id: newId, cases: formattedCases });
      await mutate();
      setCreating(false);
      setNewId("");
      setCases([{ id: "case-1", input: "", expected: "" }]);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("정말 삭제하시겠습니까?")) return;
    await datasetsApi.delete(id);
    mutate();
    if (selectedDataset?.id === id) setSelectedDataset(null);
  }

  const columns = [
    { key: "id", header: "데이터셋 ID", render: (d: any) => <span className="font-medium">{d.id}</span> },
    { key: "size", header: "크기", render: (d: any) => <span className="text-xs text-gray-500">{(d.size / 1024).toFixed(1)} KB</span> },
    { key: "last_modified", header: "최종 수정", render: (d: any) => (
      <span className="text-xs text-gray-400">
        {formatDistanceToNow(new Date(d.last_modified), { addSuffix: true, locale: ko })}
      </span>
    )},
    { key: "actions", header: "", render: (d: any) => (
      <div className="flex gap-2">
        <Button size="sm" variant="ghost" onClick={() => handleView(d.id)}>보기</Button>
        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => handleDelete(d.id)}>삭제</Button>
      </div>
    )}
  ];

  return (
    <div className="flex flex-col h-full">
      <Header
        title="평가 데이터셋"
        subtitle="LLM 성능 평가를 위한 질문 및 정답 세트 관리"
        action={<Button size="sm" onClick={() => setCreating(true)}>+ 새 데이터셋</Button>}
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {creating && (
          <Card>
            <h3 className="mb-4 text-base font-semibold">데이터셋 생성</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">데이터셋 ID (영문/숫자)</label>
                <input
                  type="text"
                  placeholder="예: logic-reasoning-v1"
                  value={newId}
                  onChange={(e) => setNewId(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div className="space-y-3">
                <label className="block text-xs font-medium text-gray-600">평가 사례 (Evaluation Cases)</label>
                {cases.map((c, idx) => (
                  <div key={idx} className="p-3 border border-gray-100 rounded-lg bg-gray-50 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-[10px] font-bold text-gray-400 uppercase">CASE {idx + 1}</span>
                      {cases.length > 1 && (
                        <button onClick={() => setCases(cases.filter((_, i) => i !== idx))} className="text-xs text-red-500">삭제</button>
                      )}
                    </div>
                    <textarea
                      placeholder="질문 (Prompt)"
                      value={c.input}
                      onChange={(e) => {
                        const next = [...cases];
                        next[idx].input = e.target.value;
                        setCases(next);
                      }}
                      className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs h-16 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <input
                      type="text"
                      placeholder="기대하는 정답 (Expected Output)"
                      value={c.expected}
                      onChange={(e) => {
                        const next = [...cases];
                        next[idx].expected = e.target.value;
                        setCases(next);
                      }}
                      className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                ))}
                <Button variant="secondary" size="sm" className="w-full" onClick={() => setCases([...cases, { id: `case-${cases.length + 1}`, input: "", expected: "" }])}>
                  + 사례 추가
                </Button>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setCreating(false)}>취소</Button>
              <Button size="sm" loading={submitting} onClick={handleCreate} disabled={!newId || cases.some(c => !c.input)}>생성 및 저장</Button>
            </div>
          </Card>
        )}

        <Table
          columns={columns as any}
          data={datasets?.data ?? []}
          keyField="id"
          loading={isLoading}
          emptyMessage="등록된 데이터셋이 없습니다."
        />

        {/* 데이터셋 상세 내역 */}
        {(selectedDataset || loadingDetails) && (
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-semibold">
                  {isEditing ? `데이터셋 수정: ${selectedDataset?.id}` : `데이터셋 상세: ${selectedDataset?.id}`}
                </h3>
                <p className="text-xs text-gray-500">포함된 평가 사례 목록</p>
              </div>
              <div className="flex gap-2">
                {!isEditing && <Button size="sm" variant="secondary" onClick={() => setIsEditing(true)}>수정하기</Button>}
                <Button size="sm" variant="ghost" onClick={() => { setSelectedDataset(null); setIsEditing(false); }}>닫기</Button>
              </div>
            </div>

            {loadingDetails ? (
              <div className="py-12 text-center text-gray-400">불러오는 중...</div>
            ) : isEditing ? (
              <div className="space-y-4">
                <div className="space-y-3">
                  {editCases.map((c, idx) => (
                    <div key={idx} className="p-3 border border-gray-100 rounded-lg bg-gray-50 space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] font-bold text-gray-400 uppercase">CASE {idx + 1}</span>
                        {editCases.length > 1 && (
                          <button onClick={() => setEditCases(editCases.filter((_, i) => i !== idx))} className="text-xs text-red-500">삭제</button>
                        )}
                      </div>
                      <textarea
                        placeholder="질문 (Prompt)"
                        value={c.input}
                        onChange={(e) => {
                          const next = [...editCases];
                          next[idx].input = e.target.value;
                          setEditCases(next);
                        }}
                        className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs h-16 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                      <input
                        type="text"
                        placeholder="기대하는 정답 (Expected Output)"
                        value={c.expected}
                        onChange={(e) => {
                          const next = [...editCases];
                          next[idx].expected = e.target.value;
                          setEditCases(next);
                        }}
                        className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                  ))}
                  <Button variant="secondary" size="sm" className="w-full" onClick={() => setEditCases([...editCases, { id: `case-${editCases.length + 1}`, input: "", expected: "" }])}>
                    + 사례 추가
                  </Button>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="ghost" size="sm" onClick={() => setIsEditing(false)}>취소</Button>
                  <Button size="sm" loading={submitting} onClick={handleEditSave} disabled={editCases.some(c => !c.input)}>변경사항 저장</Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {selectedDataset?.cases?.map((c: any, idx: number) => (
                  <div key={idx} className="p-3 border border-gray-100 rounded-lg bg-gray-50/30">
                    <div className="flex justify-between mb-1">
                      <span className="text-[10px] font-bold text-blue-600 uppercase">Case {idx + 1}</span>
                      <span className="text-[10px] text-gray-400 font-mono">{c.id}</span>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <span className="text-[9px] font-bold text-gray-400 uppercase">Input Prompt</span>
                        <p className="text-xs text-gray-700 bg-white p-2 rounded border border-gray-100 mt-0.5">
                          {c.input_messages?.[0]?.content || c.input || "No input"}
                        </p>
                      </div>
                      <div>
                        <span className="text-[9px] font-bold text-gray-400 uppercase">Expected Output</span>
                        <p className="text-xs text-gray-900 font-medium mt-0.5">
                          {c.expected_output || c.expected || "(정답 정의 없음)"}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
