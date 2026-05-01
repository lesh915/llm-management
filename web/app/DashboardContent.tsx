"use client";

import useSWR from "swr";
import { StatsCard } from "@/components/dashboard/StatsCard";
import { Card, CardHeader } from "@/components/ui/Card";
import { SeverityBadge, StatusBadge } from "@/components/ui/Badge";
import { modelsApi, eventsApi, tasksApi, healthApi } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";

function ServiceDot({ status }: { status: string }) {
  const color = status === "ok" ? "bg-green-500" : status === "degraded" ? "bg-yellow-500" : "bg-red-500";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} />;
}

export function DashboardContent() {
  const { data: models } = useSWR("models", () => modelsApi.list());
  const { data: events } = useSWR("events-recent", () =>
    eventsApi.list({ limit: 5 })
  );
  const { data: tasks } = useSWR("tasks", () => tasksApi.list());
  const { data: health } = useSWR("health", () => healthApi.upstream(), {
    refreshInterval: 30_000,
  });

  const activeModels   = models?.data.filter((m) => m.status === "active").length ?? 0;
  const totalModels    = models?.data.length ?? 0;
  const openEvents     = events?.data.filter((e) => e.status === "open").length ?? 0;
  const completedTasks = tasks?.data.filter((t) => t.status === "completed").length ?? 0;

  return (
    <div className="space-y-6">
      {/* 통계 카드 */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatsCard
          title="등록된 모델"
          value={totalModels}
          subtitle={`활성 ${activeModels}개`}
          color="blue"
          icon={
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
            </svg>
          }
        />
        <StatsCard
          title="열린 이벤트"
          value={openEvents}
          subtitle="즉시 처리 필요"
          color={openEvents > 0 ? "red" : "green"}
          icon={
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          }
        />
        <StatsCard
          title="비교 완료"
          value={completedTasks}
          subtitle={`전체 ${tasks?.data.length ?? 0}개 중`}
          color="green"
          icon={
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          }
        />
        <StatsCard
          title="서비스 상태"
          value={health ? (health.status === "ok" ? "정상" : "이상") : "확인 중"}
          subtitle={`${Object.values(health?.services ?? {}).filter((s) => s.status === "ok").length} / ${Object.keys(health?.services ?? {}).length} 정상`}
          color={health?.status === "ok" ? "green" : "yellow"}
          icon={
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 최근 AIOps 이벤트 */}
        <Card>
          <CardHeader title="최근 이벤트" subtitle="AIOps 모니터링" />
          <div className="space-y-3">
            {!events?.data.length ? (
              <p className="text-sm text-gray-400 text-center py-4">최근 이벤트가 없습니다.</p>
            ) : (
              events.data.map((ev) => (
                <div key={ev.id} className="flex items-start gap-3 rounded-lg border border-gray-100 p-3">
                  <SeverityBadge severity={ev.severity} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">{ev.event_type}</p>
                    <p className="text-xs text-gray-500 truncate">{ev.description}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <StatusBadge status={ev.status} />
                    <span className="text-xs text-gray-400">
                      {formatDistanceToNow(new Date(ev.created_at), { addSuffix: true, locale: ko })}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* 서비스 상태 */}
        <Card>
          <CardHeader title="서비스 상태" subtitle="업스트림 헬스체크" />
          <div className="space-y-2">
            {!health ? (
              <p className="text-sm text-gray-400 text-center py-4">확인 중...</p>
            ) : (
              Object.entries(health.services).map(([name, info]) => (
                <div key={name} className="flex items-center justify-between rounded-lg border border-gray-100 px-4 py-2.5">
                  <div className="flex items-center gap-2.5">
                    <ServiceDot status={info.status} />
                    <span className="text-sm font-medium text-gray-700">{name}</span>
                  </div>
                  <span className={`text-xs font-medium ${
                    info.status === "ok" ? "text-green-600" :
                    info.status === "degraded" ? "text-yellow-600" : "text-red-600"
                  }`}>
                    {info.status === "ok" ? "정상" :
                     info.status === "degraded" ? "저하" : "연결 불가"}
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
