"use client";

import useSWR from "swr";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Card } from "@/components/ui/Card";
import { Table } from "@/components/ui/Table";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { modelsApi, type Model } from "@/lib/api";
import { MODEL_CATALOG_BY_PROVIDER, type ModelPreset } from "@/lib/modelCatalog";

// ── Types ─────────────────────────────────────────────────────────────────────

type ModelType = "cloud" | "local";
type CloudProvider = "Anthropic" | "OpenAI" | "Google" | "custom";
type LocalProvider = "Ollama" | "vLLM" | "LM Studio" | "LocalAI";

interface FormState {
  modelType: ModelType;
  // common
  id: string;
  family: string;
  version: string;
  // cloud
  cloudProvider: CloudProvider;
  apiKey: string;
  endpoint: string;
  // local
  localProvider: LocalProvider;
  ollamaBaseUrl: string;
  modelName: string;
  // capabilities
  contextWindow: string;
  maxOutputTokens: string;
  vision: boolean;
  toolUse: boolean;
  streaming: boolean;
  structuredOutput: boolean;
  // pricing
  inputPrice: string;
  outputPrice: string;
  // characteristics
  reasoningDepth: string;
  instructionFollowing: string;
  codeGeneration: string;
  latencyTier: string;
}

const DEFAULT_FORM: FormState = {
  modelType: "cloud",
  id: "",
  family: "",
  version: "",
  cloudProvider: "OpenAI",
  apiKey: "",
  endpoint: "",
  localProvider: "Ollama",
  ollamaBaseUrl: "http://host.docker.internal:11434",
  modelName: "",
  contextWindow: "128000",
  maxOutputTokens: "4096",
  vision: false,
  toolUse: true,
  streaming: true,
  structuredOutput: false,
  inputPrice: "0",
  outputPrice: "0",
  reasoningDepth: "medium",
  instructionFollowing: "medium",
  codeGeneration: "medium",
  latencyTier: "medium",
};

const CLOUD_PROVIDERS: { value: CloudProvider; label: string; defaultEndpoint?: string }[] = [
  { value: "OpenAI",     label: "OpenAI (GPT)",       defaultEndpoint: "https://api.openai.com/v1" },
  { value: "Anthropic",  label: "Anthropic (Claude)",  defaultEndpoint: "https://api.anthropic.com/v1" },
  { value: "Google",     label: "Google (Gemini)",     defaultEndpoint: "https://generativelanguage.googleapis.com/v1beta/openai" },
  { value: "custom",     label: "커스텀 (OpenAI 호환)" },
];

const LOCAL_PROVIDERS: { value: LocalProvider; label: string }[] = [
  { value: "Ollama",    label: "Ollama" },
  { value: "vLLM",      label: "vLLM" },
  { value: "LM Studio", label: "LM Studio" },
  { value: "LocalAI",   label: "LocalAI" },
];

const LEVELS = ["low", "medium", "high"] as const;
const LATENCY_TIERS = ["low", "medium", "high"] as const;

// ── Helper Components ─────────────────────────────────────────────────────────

function CapabilityDot({ ok }: { ok: unknown }) {
  return ok
    ? <span className="text-green-500 font-bold">✓</span>
    : <span className="text-gray-300">—</span>;
}

function FormLabel({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-gray-600 mb-1">{children}</label>;
}

function FormInput({ ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full text-sm border border-gray-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
    />
  );
}

function FormSelect({ children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="w-full text-sm border border-gray-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
    >
      {children}
    </select>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <div
        onClick={onChange}
        className={`relative w-9 h-5 rounded-full transition-colors ${checked ? "bg-blue-500" : "bg-gray-300"}`}
      >
        <div className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-4" : "translate-x-0"}`} />
      </div>
      <span className="text-sm text-gray-700">{label}</span>
    </label>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ModelsPage() {
  const { data, isLoading, mutate } = useSWR("models", () => modelsApi.list());
  const [selected, setSelected] = useState<Model | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("http://host.docker.internal:11434");
  const [importingOllama, setImportingOllama] = useState(false);
  const [appliedPreset, setAppliedPreset] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: "success" | "error" | null; message: string }>({ status: null, message: "" });

  function set(key: keyof FormState, value: unknown) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  function handleProviderChange(v: CloudProvider) {
    const found = CLOUD_PROVIDERS.find(p => p.value === v);
    setAppliedPreset(null);
    set("cloudProvider", v);
    if (found?.defaultEndpoint) set("endpoint", found.defaultEndpoint);
    else set("endpoint", "");
  }

  function applyPreset(preset: ModelPreset) {
    setAppliedPreset(preset.id);
    setForm(prev => ({
      ...prev,
      id: preset.id,
      family: preset.family,
      version: preset.version,
      cloudProvider: preset.provider as CloudProvider,
      endpoint: preset.endpoint,
      contextWindow: String(preset.contextWindow),
      maxOutputTokens: String(preset.maxOutputTokens),
      vision: preset.vision,
      toolUse: preset.toolUse,
      streaming: preset.streaming,
      structuredOutput: preset.structuredOutput,
      inputPrice: String(preset.inputPrice),
      outputPrice: String(preset.outputPrice),
      reasoningDepth: preset.reasoningDepth,
      instructionFollowing: preset.instructionFollowing,
      codeGeneration: preset.codeGeneration,
      latencyTier: preset.latencyTier,
    }));
  }

  async function handleSubmit() {
    setError("");
    if (!form.id.trim()) { setError("모델 ID를 입력해주세요."); return; }

    setSubmitting(true);
    try {
      const isLocal = form.modelType === "local";
      const provider = isLocal ? form.localProvider : form.cloudProvider;

      const body: Record<string, unknown> = {
        id: form.id.trim(),
        provider,
        family: form.family.trim() || undefined,
        version: form.version.trim() || undefined,
        is_custom: isLocal || form.cloudProvider === "custom",
        capabilities: {
          context_window: parseInt(form.contextWindow) || 0,
          max_output_tokens: parseInt(form.maxOutputTokens) || 0,
          vision: form.vision,
          tool_use: form.toolUse,
          streaming: form.streaming,
          structured_output: form.structuredOutput,
          parallel_tool_calls: false,
          extended_thinking: false,
        },
        characteristics: {
          reasoning_depth: form.reasoningDepth,
          instruction_following: form.instructionFollowing,
          code_generation: form.codeGeneration,
          latency_tier: form.latencyTier,
        },
        pricing: {
          input_per_1m_tokens: parseFloat(form.inputPrice) || 0,
          output_per_1m_tokens: parseFloat(form.outputPrice) || 0,
        },
        api: {
          endpoint: isLocal ? form.ollamaBaseUrl : form.endpoint,
          model_name: isLocal ? (form.modelName || form.id) : form.id,
          auth_type: isLocal ? "none" : "api_key",
          api_key: (!isLocal && form.apiKey) ? form.apiKey : undefined,
          openai_compat: form.cloudProvider === "custom" || isLocal,
        },
      };

      await modelsApi.create(body as Partial<Model>);
      await mutate();
      setShowAddModal(false);
      setForm(DEFAULT_FORM);
    } catch (e: any) {
      setError(e.message ?? "등록에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTestConnection() {
    setTesting(true);
    setTestResult({ status: null, message: "" });
    try {
      const isLocal = form.modelType === "local";
      const provider = isLocal ? form.localProvider : form.cloudProvider;

      const body = {
        id: form.id.trim() || "test-id",
        provider,
        is_custom: isLocal || form.cloudProvider === "custom",
        capabilities: {
          context_window: parseInt(form.contextWindow) || 1, // Must be > 0
          max_output_tokens: parseInt(form.maxOutputTokens) || 1, // Must be > 0
          vision: form.vision,
          tool_use: form.toolUse,
          streaming: form.streaming,
          structured_output: form.structuredOutput,
        },
        characteristics: {
          reasoning_depth: form.reasoningDepth,
          instruction_following: form.instructionFollowing,
          code_generation: form.codeGeneration,
          latency_tier: form.latencyTier,
        },
        pricing: {
          input_per_1m_tokens: parseFloat(form.inputPrice) || 0,
          output_per_1m_tokens: parseFloat(form.outputPrice) || 0,
        },
        api: {
          endpoint: isLocal ? form.ollamaBaseUrl : form.endpoint,
          model_name: isLocal ? (form.modelName || form.id) : form.id,
          auth_type: isLocal ? "none" : "api_key",
          api_key: (!isLocal && form.apiKey) ? form.apiKey : undefined,
          openai_compat: form.cloudProvider === "custom" || isLocal,
        },
      };

      const res = await modelsApi.testConnection(body);
      setTestResult({ status: res.status, message: res.message });
    } catch (e: any) {
      setTestResult({ status: "error", message: e.message ?? "테스트 중 오류가 발생했습니다." });
    } finally {
      setTesting(false);
    }
  }

  async function handleOllamaImport() {
    setImportingOllama(true);
    try {
      const res = await fetch("/api/models/import/ollama", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base_url: ollamaUrl }),
      });
      const json = await res.json();
      await mutate();
      const cnt = json?.data?.registered?.length ?? 0;
      alert(`Ollama 모델 ${cnt}개를 가져왔습니다.`);
    } catch {
      alert("Ollama 모델 가져오기에 실패했습니다.");
    } finally {
      setImportingOllama(false);
    }
  }

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
        action={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => setShowAddModal(true)}>
              + 모델 등록
            </Button>
          </div>
        }
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

            <div className="pt-4 border-t border-gray-100 space-y-2">
              {selected.status === "active" && (
                <Button
                  variant="secondary"
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
              <Button
                variant="danger"
                size="sm"
                className="w-full"
                onClick={async () => {
                  if (!confirm(`정말 '${selected.id}' 모델을 삭제하시겠습니까?`)) return;
                  try {
                    await modelsApi.delete(selected.id);
                    mutate();
                    setSelected(null);
                  } catch (err) {
                    alert("삭제 중 오류가 발생했습니다.");
                  }
                }}
              >
                영구 삭제
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* ── 모델 등록 모달 ─────────────────────────────────────────────── */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">모델 등록</h2>
                <p className="text-xs text-gray-400 mt-0.5">로컬 LLM 또는 외부 클라우드 모델을 등록합니다</p>
              </div>
              <button onClick={() => { setShowAddModal(false); setError(""); }} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
            </div>

            <div className="px-6 py-5 space-y-6">
              {/* 모델 유형 탭 */}
              <div className="flex rounded-lg border border-gray-200 overflow-hidden">
                {[
                  { value: "cloud" as ModelType, label: "☁️  외부 클라우드 LLM", desc: "OpenAI, Anthropic, Google 등" },
                  { value: "local" as ModelType, label: "🖥️  로컬 LLM",           desc: "Ollama, vLLM, LM Studio 등" },
                ].map(tab => (
                  <button
                    key={tab.value}
                    onClick={() => set("modelType", tab.value)}
                    className={`flex-1 py-3 px-4 text-left transition-colors ${
                      form.modelType === tab.value
                        ? "bg-blue-50 border-b-2 border-blue-500"
                        : "bg-gray-50 hover:bg-gray-100"
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-800">{tab.label}</p>
                    <p className="text-xs text-gray-400">{tab.desc}</p>
                  </button>
                ))}
              </div>

              {/* 프리셋 선택 (클라우드 전용) */}
              {form.modelType === "cloud" && (
                <div className="border border-blue-100 bg-blue-50/50 rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase text-blue-600 tracking-wide">📋 모델 프리셋 선택</p>
                    {appliedPreset && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                        ✓ {appliedPreset} 적용됨
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-blue-500">모델을 선택하면 기능·가격·특성 정보가 자동으로 채워집니다. API 키는 직접 입력하세요.</p>
                  {Object.entries(MODEL_CATALOG_BY_PROVIDER).map(([provider, presets]) => (
                    <div key={provider}>
                      <p className="text-xs font-medium text-gray-500 mb-1.5">{provider}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {presets.map(preset => (
                          <button
                            key={preset.id}
                            onClick={() => applyPreset(preset)}
                            title={preset.description}
                            className={`px-3 py-1.5 text-xs rounded-full border transition-all ${
                              appliedPreset === preset.id
                                ? "bg-blue-500 text-white border-blue-500 shadow-sm"
                                : "bg-white border-gray-200 text-gray-700 hover:border-blue-300 hover:bg-blue-50"
                            }`}
                          >
                            {preset.label}
                            <span className="ml-1.5 opacity-60 font-mono">
                              ${preset.inputPrice}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Ollama 자동 가져오기 (로컬 전용) */}
              {form.modelType === "local" && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-amber-800 mb-2">🔍 Ollama 자동 가져오기</p>
                  <div className="flex gap-2">
                    <input
                      value={ollamaUrl}
                      onChange={e => setOllamaUrl(e.target.value)}
                      placeholder="http://host.docker.internal:11434"
                      className="flex-1 text-sm border border-amber-300 rounded px-3 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-amber-400"
                    />
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={handleOllamaImport}
                      disabled={importingOllama}
                    >
                      {importingOllama ? "가져오는 중..." : "가져오기"}
                    </Button>
                  </div>
                  <p className="text-xs text-amber-600 mt-1">또는 아래 양식으로 모델을 직접 등록하세요</p>
                </div>
              )}

              {/* 공급자 선택 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <FormLabel>{form.modelType === "local" ? "로컬 런타임" : "클라우드 공급자"}</FormLabel>
                  {form.modelType === "cloud" ? (
                    <FormSelect value={form.cloudProvider} onChange={e => handleProviderChange(e.target.value as CloudProvider)}>
                      {CLOUD_PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                    </FormSelect>
                  ) : (
                    <FormSelect value={form.localProvider} onChange={e => set("localProvider", e.target.value)}>
                      {LOCAL_PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                    </FormSelect>
                  )}
                </div>

                <div>
                  <FormLabel>모델 ID <span className="text-red-400">*</span></FormLabel>
                  <FormInput
                    value={form.id}
                    onChange={e => set("id", e.target.value)}
                    placeholder={form.modelType === "local" ? "ollama/qwen3.5:latest" : "gpt-4o"}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <FormLabel>패밀리 (선택)</FormLabel>
                  <FormInput value={form.family} onChange={e => set("family", e.target.value)} placeholder="GPT-4, Claude 3 등" />
                </div>
                <div>
                  <FormLabel>버전 (선택)</FormLabel>
                  <FormInput value={form.version} onChange={e => set("version", e.target.value)} placeholder="4o, 3.5, latest 등" />
                </div>
              </div>

              {/* API 설정 */}
              <div className="border border-gray-100 rounded-lg p-4 space-y-3">
                <p className="text-xs font-semibold uppercase text-gray-500 tracking-wide">API 설정</p>
                {form.modelType === "local" ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <FormLabel>엔드포인트 URL</FormLabel>
                      <FormInput value={form.ollamaBaseUrl} onChange={e => set("ollamaBaseUrl", e.target.value)} placeholder="http://localhost:11434" />
                    </div>
                    <div>
                      <FormLabel>모델명 (런타임 내)</FormLabel>
                      <FormInput value={form.modelName} onChange={e => set("modelName", e.target.value)} placeholder="qwen3.5:latest" />
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <FormLabel>API 엔드포인트</FormLabel>
                      <FormInput value={form.endpoint} onChange={e => set("endpoint", e.target.value)} placeholder="https://api.openai.com/v1" />
                    </div>
                    <div>
                      <FormLabel>API 키</FormLabel>
                      <FormInput type="password" value={form.apiKey} onChange={e => set("apiKey", e.target.value)} placeholder="sk-..." />
                    </div>
                  </div>
                )}
              </div>

              {/* 기능 설정 */}
              <div className="border border-gray-100 rounded-lg p-4 space-y-4">
                <p className="text-xs font-semibold uppercase text-gray-500 tracking-wide">기능 (Capabilities)</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <FormLabel>컨텍스트 윈도우 (토큰)</FormLabel>
                    <FormInput type="number" value={form.contextWindow} onChange={e => set("contextWindow", e.target.value)} />
                  </div>
                  <div>
                    <FormLabel>최대 출력 토큰</FormLabel>
                    <FormInput type="number" value={form.maxOutputTokens} onChange={e => set("maxOutputTokens", e.target.value)} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Toggle checked={form.toolUse} onChange={() => set("toolUse", !form.toolUse)} label="도구 호출 (Tool Use)" />
                  <Toggle checked={form.vision} onChange={() => set("vision", !form.vision)} label="이미지 이해 (Vision)" />
                  <Toggle checked={form.streaming} onChange={() => set("streaming", !form.streaming)} label="스트리밍" />
                  <Toggle checked={form.structuredOutput} onChange={() => set("structuredOutput", !form.structuredOutput)} label="구조화 출력" />
                </div>
              </div>

              {/* 가격 */}
              <div className="border border-gray-100 rounded-lg p-4 space-y-3">
                <p className="text-xs font-semibold uppercase text-gray-500 tracking-wide">가격 (USD / 1M 토큰, 로컬은 0)</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <FormLabel>입력 토큰</FormLabel>
                    <FormInput type="number" step="0.01" value={form.inputPrice} onChange={e => set("inputPrice", e.target.value)} placeholder="3.00" />
                  </div>
                  <div>
                    <FormLabel>출력 토큰</FormLabel>
                    <FormInput type="number" step="0.01" value={form.outputPrice} onChange={e => set("outputPrice", e.target.value)} placeholder="15.00" />
                  </div>
                </div>
              </div>

              {/* 특성 */}
              <div className="border border-gray-100 rounded-lg p-4 space-y-3">
                <p className="text-xs font-semibold uppercase text-gray-500 tracking-wide">특성 (Characteristics)</p>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: "reasoningDepth",       label: "추론 깊이" },
                    { key: "instructionFollowing",  label: "지시 이해" },
                    { key: "codeGeneration",        label: "코드 생성" },
                    { key: "latencyTier",           label: "지연시간" },
                  ].map(({ key, label }) => (
                    <div key={key}>
                      <FormLabel>{label}</FormLabel>
                      <FormSelect value={(form as any)[key]} onChange={e => set(key as keyof FormState, e.target.value)}>
                        {(key === "latencyTier" ? LATENCY_TIERS : LEVELS).map(l => (
                          <option key={l} value={l}>{l}</option>
                        ))}
                      </FormSelect>
                    </div>
                  ))}
                </div>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
                  {error}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-xl space-y-3">
              {testResult.status && (
                <div className={`text-xs px-3 py-2 rounded-md border ${
                  testResult.status === "success" 
                    ? "bg-green-50 border-green-200 text-green-700" 
                    : "bg-red-50 border-red-200 text-red-700"
                }`}>
                  <span className="font-bold">{testResult.status === "success" ? "✓ 성공: " : "✕ 실패: "}</span>
                  {testResult.message}
                </div>
              )}
              <div className="flex justify-end gap-3">
                <Button variant="ghost" onClick={() => { setShowAddModal(false); setError(""); setTestResult({ status: null, message: "" }); }}>
                  취소
                </Button>
                <Button variant="secondary" onClick={handleTestConnection} disabled={testing || submitting}>
                  {testing ? "연결 확인 중..." : "연결 테스트"}
                </Button>
                <Button onClick={handleSubmit} disabled={submitting || testing}>
                  {submitting ? "등록 중..." : "모델 등록"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
