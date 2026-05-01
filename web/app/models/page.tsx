"use client";

import useSWR from "swr";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { modelsApi, type Model } from "@/lib/api";

function CapabilityDot({ ok }: { ok: unknown }) {
  return ok
    ? <span className="text-green-500 font-bold">✓</span>
    : <span className="text-gray-300">—</span>;
}

export default function ModelsPage() {
  const { data, isLoading, mutate } = useSWR("models", () => modelsApi.list());
  const [selected, setSelected] = useState<Model | null>(null);

  const columns = [
    {
      key: "id",
      header: "모델 ID",
      render: (m: Model) => (
        <span className="font-mono text-xs font-medium text-blue-700">{m.id}</span>
      ),
    },
    {
      key: "provider",
      header: "공급자",
      render: (m: Model) => (
        <div>
          <p className="text-sm font-medium">{m.provider}</p>
          {m.family && <p className="text-xs text-gray-400">{m.family} {m.version}</p>}
        </div>
      ),
    },
    {
      key: "status",
      header: "상태",
      render: (m: Model) => <StatusBadge status={m.status} />,
    },
    {
      key: "tool_use",
      header: "도구 호출",
      render: (m: Model) => <CapabilityDot ok={m.capabilities?.tool_use} />,
    },
    {
      key: "vision",
      header: "비전",
      render: (m: Model) => <CapabilityDot ok={m.capabilities?.vision} />,
    },
    {
      key: "context_window",
      header: "컨텍스트",
      render: (m: Model) => (
        <span className="text-xs font-mono">
          {m.capabilities?.context_window
            ? `${((m.capabilities.context_window as number) / 1000).toFixed(0)}K`
            : "—"}
        </span>
      ),
    },
    {
      key: "pricing",
      header: "입력 / 출력 ($/1M)",
      render: (m: Model) => (
        <span className="text-xs font-mono text-gray-600">
          ${m.pricing.input_per_1m_tokens} / ${m.pricing.output_per_1m_tokens}
        </span>
      ),
    },
    {
      key: "is_custom",
      header: "유형",
      render: (m: Model) => (
        <Badge variant={m.is_custom ? "purple" : "blue"}>
          {m.is_custom ? "로컬" : "클라우드"}
        </Badge>
      ),
    },
  ];

  return (
    <div className="flex flex-col h-full">
      <Header
        title="모델 레지스트리"
        subtitle={`등록된 LLM 모델 ${data?.data.length ?? 0}개`}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* 목록 */}
        <div className="flex-1 overflow-y-auto p-6">
          <Table
            columns={columns as never}
            data={(data?.data ?? []) as never[]}
            keyField="id"
            loading={isLoading}
            onRowClick={(m) => setSelected(m as unknown as Model)}
            emptyMessage="등록된 모델이 없습니다."
          />
        </div>

        {/* 상세 패널 */}
        {selected && (
          <div className="w-80 border-l border-gray-200 bg-white overflow-y-auto p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">상세 정보</h3>
              <button
                onClick={() => setSelected(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div>
              <p className="text-xs font-medium uppercase text-gray-400 mb-1">모델 ID</p>
              <p className="font-mono text-sm text-blue-700 break-all">{selected.id}</p>
            </div>

            <div>
              <p className="text-xs font-medium uppercase text-gray-400 mb-1">공급자</p>
              <p className="text-sm">{selected.provider} {selected.family} {selected.version}</p>
            </div>

            <div>
              <p className="text-xs font-medium uppercase text-gray-400 mb-2">기능</p>
              <div className="space-y-1">
                {Object.entries(selected.capabilities).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">{k}</span>
                    <span className="font-mono text-xs">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs font-medium uppercase text-gray-400 mb-2">특성</p>
              <div className="space-y-1">
                {Object.entries(selected.characteristics).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">{k}</span>
                    <Badge variant="gray">{String(v)}</Badge>
                  </div>
                ))}
              </div>
            </div>

            {selected.status === "active" && (
              <Button
                variant="danger"
                size="sm"
                className="w-full"
                onClick={async () => {
                  await modelsApi.patchStatus(selected.id, "deprecated");
                  mutate();
                  setSelected(null);
                }}
              >
                Deprecated 처리
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
