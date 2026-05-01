"use client";

import useSWR from "swr";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card, CardHeader } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import { SeverityBadge, StatusBadge, Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { eventsApi, rulesApi, type AIOpsEvent, type Rule } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";

type Tab = "events" | "rules";

export default function AIOpsPage() {
  const [tab, setTab] = useState<Tab>("events");
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<AIOpsEvent | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const { data: events, isLoading: eventsLoading, mutate: mutateEvents } = useSWR(
    ["events", statusFilter, severityFilter],
    () => eventsApi.list({
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(severityFilter ? { severity: severityFilter } : {}),
      limit: 50,
    }),
    { refreshInterval: 15_000 }
  );

  const { data: rules, isLoading: rulesLoading, mutate: mutateRules } = useSWR(
    "rules",
    () => rulesApi.list()
  );

  async function handleDiagnose(eventId: string) {
    setActionLoading(true);
    try {
      await eventsApi.diagnose(eventId);
      await mutateEvents();
    } finally {
      setActionLoading(false);
    }
  }

  async function handleApprove(event: AIOpsEvent, actionIndex: number, approved: boolean) {
    setActionLoading(true);
    try {
      await eventsApi.approve(event.id, { action_index: actionIndex, approved });
      await mutateEvents();
      setSelectedEvent(null);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleResolve(eventId: string) {
    await eventsApi.resolve(eventId);
    await mutateEvents();
    setSelectedEvent(null);
  }

  async function toggleRule(rule: Rule) {
    await rulesApi.update(rule.id, { enabled: !rule.enabled });
    mutateRules();
  }

  const eventColumns = [
    {
      key: "event_type",
      header: "유형",
      render: (e: AIOpsEvent) => (
        <span className="text-sm font-mono font-medium text-gray-800">{e.event_type}</span>
      ),
    },
    {
      key: "severity",
      header: "심각도",
      render: (e: AIOpsEvent) => <SeverityBadge severity={e.severity} />,
    },
    {
      key: "status",
      header: "상태",
      render: (e: AIOpsEvent) => <StatusBadge status={e.status} />,
    },
    {
      key: "description",
      header: "설명",
      render: (e: AIOpsEvent) => (
        <span className="text-xs text-gray-500 truncate max-w-xs block">{e.description}</span>
      ),
    },
    {
      key: "created_at",
      header: "발생 시각",
      render: (e: AIOpsEvent) => (
        <span className="text-xs text-gray-400">
          {formatDistanceToNow(new Date(e.created_at), { addSuffix: true, locale: ko })}
        </span>
      ),
    },
    {
      key: "actions_count",
      header: "제안된 조치",
      render: (e: AIOpsEvent) => (
        <span className="text-xs text-gray-500">{e.actions.length}개</span>
      ),
    },
  ];

  const ruleColumns = [
    {
      key: "name",
      header: "규칙명",
      render: (r: Rule) => <span className="text-sm font-medium">{r.name}</span>,
    },
    {
      key: "action.type",
      header: "조치",
      render: (r: Rule) => (
        <Badge variant="blue">{r.action.type}</Badge>
      ),
    },
    {
      key: "requires_approval",
      header: "승인 필요",
      render: (r: Rule) => (
        <Badge variant={r.requires_approval ? "orange" : "green"}>
          {r.requires_approval ? "필요" : "자동"}
        </Badge>
      ),
    },
    {
      key: "enabled",
      header: "상태",
      render: (r: Rule) => (
        <button
          onClick={() => toggleRule(r)}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
            r.enabled ? "bg-blue-600" : "bg-gray-200"
          }`}
        >
          <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            r.enabled ? "translate-x-4" : "translate-x-1"
          }`} />
        </button>
      ),
    },
  ];

  return (
    <div className="flex flex-col h-full">
      <Header title="AIOps" subtitle="이상 감지 및 자동 조치 관리" />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* 탭 */}
          <div className="flex gap-1 rounded-lg bg-gray-100 p-1 w-fit">
            {(["events", "rules"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  tab === t ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {t === "events" ? "이벤트" : "자동화 규칙"}
              </button>
            ))}
          </div>

          {tab === "events" && (
            <>
              {/* 필터 */}
              <div className="flex gap-3">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                >
                  <option value="">전체 상태</option>
                  {["open", "diagnosing", "pending_approval", "executing", "resolved"].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                >
                  <option value="">전체 심각도</option>
                  {["low", "medium", "high", "critical"].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <Table
                columns={eventColumns as never}
                data={(events?.data ?? []) as never[]}
                keyField="id"
                loading={eventsLoading}
                onRowClick={(e) => setSelectedEvent(e as unknown as AIOpsEvent)}
                emptyMessage="이벤트가 없습니다."
              />
            </>
          )}

          {tab === "rules" && (
            <Table
              columns={ruleColumns as never}
              data={(rules?.data ?? []) as never[]}
              keyField="id"
              loading={rulesLoading}
              emptyMessage="자동화 규칙이 없습니다."
            />
          )}
        </div>

        {/* 이벤트 상세 패널 */}
        {selectedEvent && (
          <div className="w-96 border-l border-gray-200 bg-white overflow-y-auto p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">이벤트 상세</h3>
              <button onClick={() => setSelectedEvent(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>

            <div className="space-y-3">
              <div className="flex gap-2">
                <SeverityBadge severity={selectedEvent.severity} />
                <StatusBadge status={selectedEvent.status} />
              </div>

              <div>
                <p className="text-xs font-medium uppercase text-gray-400 mb-1">유형</p>
                <p className="font-mono text-sm">{selectedEvent.event_type}</p>
              </div>

              {selectedEvent.description && (
                <div>
                  <p className="text-xs font-medium uppercase text-gray-400 mb-1">설명</p>
                  <p className="text-sm text-gray-700">{selectedEvent.description}</p>
                </div>
              )}

              {selectedEvent.model_id && (
                <div>
                  <p className="text-xs font-medium uppercase text-gray-400 mb-1">모델</p>
                  <p className="font-mono text-sm text-blue-700">{selectedEvent.model_id}</p>
                </div>
              )}

              <div>
                <p className="text-xs font-medium uppercase text-gray-400 mb-1">발생 시각</p>
                <p className="text-xs text-gray-500">
                  {new Date(selectedEvent.created_at).toLocaleString("ko-KR")}
                </p>
              </div>
            </div>

            {/* 제안된 조치 */}
            {selectedEvent.actions.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase text-gray-400 mb-2">제안된 조치</p>
                <div className="space-y-2">
                  {selectedEvent.actions.map((action, idx) => (
                    <div key={idx} className="rounded-lg border border-gray-200 p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <Badge variant="blue">{String(action.action ?? action.type)}</Badge>
                        {!!action.confidence && (
                          <Badge variant={action.confidence === "high" ? "green" : action.confidence === "medium" ? "yellow" : "gray"}>
                            {String(action.confidence)}
                          </Badge>
                        )}
                      </div>
                      {!!action.reason && (
                        <p className="text-xs text-gray-600">{String(action.reason)}</p>
                      )}
                      {selectedEvent.status === "pending_approval" && !action.approved && (
                        <div className="flex gap-2 pt-1">
                          <Button
                            size="sm"
                            loading={actionLoading}
                            onClick={() => handleApprove(selectedEvent, idx, true)}
                          >
                            승인
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            loading={actionLoading}
                            onClick={() => handleApprove(selectedEvent, idx, false)}
                          >
                            거부
                          </Button>
                        </div>
                      )}
                      {!!action.approved && (
                        <Badge variant="green">승인됨</Badge>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 액션 버튼 */}
            <div className="space-y-2 pt-2">
              {selectedEvent.status === "open" && (
                <Button
                  className="w-full"
                  size="sm"
                  loading={actionLoading}
                  onClick={() => handleDiagnose(selectedEvent.id)}
                >
                  AI 진단 시작
                </Button>
              )}
              {!["resolved"].includes(selectedEvent.status) && (
                <Button
                  className="w-full"
                  size="sm"
                  variant="secondary"
                  onClick={() => handleResolve(selectedEvent.id)}
                >
                  해결됨으로 처리
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
