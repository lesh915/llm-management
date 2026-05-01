import { Header } from "@/components/layout/Header";
import { StatsCard } from "@/components/dashboard/StatsCard";
import { DashboardContent } from "./DashboardContent";

export default function DashboardPage() {
  return (
    <div className="flex flex-col h-full">
      <Header
        title="대시보드"
        subtitle="LLM Management Platform 운영 현황"
      />
      <div className="flex-1 p-6 space-y-6">
        <DashboardContent />
      </div>
    </div>
  );
}
