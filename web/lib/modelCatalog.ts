/**
 * 주요 클라우드 LLM 사전 정보 카탈로그
 * 출처: 각 공급자 공식 문서 (2025년 기준)
 */

export interface ModelPreset {
  id: string;
  label: string;               // 사용자에게 표시할 이름
  provider: "OpenAI" | "Anthropic" | "Google" | "custom";
  family: string;
  version: string;
  endpoint: string;
  contextWindow: number;       // tokens
  maxOutputTokens: number;
  vision: boolean;
  toolUse: boolean;
  streaming: boolean;
  structuredOutput: boolean;
  inputPrice: number;          // USD per 1M tokens
  outputPrice: number;
  reasoningDepth: "low" | "medium" | "high";
  instructionFollowing: "low" | "medium" | "high";
  codeGeneration: "low" | "medium" | "high";
  latencyTier: "low" | "medium" | "high";
  description: string;
}

// ── OpenAI ───────────────────────────────────────────────────────────────────

const OPENAI_ENDPOINT = "https://api.openai.com/v1";

const OPENAI_MODELS: ModelPreset[] = [
  {
    id: "gpt-4o",
    label: "GPT-4o",
    provider: "OpenAI",
    family: "GPT-4",
    version: "4o",
    endpoint: OPENAI_ENDPOINT,
    contextWindow: 128000,
    maxOutputTokens: 16384,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: true,
    inputPrice: 2.50,
    outputPrice: 10.00,
    reasoningDepth: "high",
    instructionFollowing: "high",
    codeGeneration: "high",
    latencyTier: "medium",
    description: "OpenAI 최신 멀티모달 플래그십 모델. 텍스트·이미지·오디오 처리.",
  },
  {
    id: "gpt-4o-mini",
    label: "GPT-4o mini",
    provider: "OpenAI",
    family: "GPT-4",
    version: "4o-mini",
    endpoint: OPENAI_ENDPOINT,
    contextWindow: 128000,
    maxOutputTokens: 16384,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: true,
    inputPrice: 0.15,
    outputPrice: 0.60,
    reasoningDepth: "medium",
    instructionFollowing: "high",
    codeGeneration: "medium",
    latencyTier: "low",
    description: "GPT-4o의 경량화 버전. 빠르고 비용 효율적.",
  },
  {
    id: "gpt-4-turbo",
    label: "GPT-4 Turbo",
    provider: "OpenAI",
    family: "GPT-4",
    version: "turbo",
    endpoint: OPENAI_ENDPOINT,
    contextWindow: 128000,
    maxOutputTokens: 4096,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: false,
    inputPrice: 10.00,
    outputPrice: 30.00,
    reasoningDepth: "high",
    instructionFollowing: "high",
    codeGeneration: "high",
    latencyTier: "medium",
    description: "지식 컷오프 2024년 4월. 큰 컨텍스트 처리에 강점.",
  },
];

// ── Anthropic ─────────────────────────────────────────────────────────────────

const ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1";

const ANTHROPIC_MODELS: ModelPreset[] = [
  {
    id: "claude-opus-4-7",
    label: "Claude 4.7 Opus",
    provider: "Anthropic",
    family: "Claude 4",
    version: "4.7 Opus",
    endpoint: ANTHROPIC_ENDPOINT,
    contextWindow: 200000,
    maxOutputTokens: 32000,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: true,
    inputPrice: 15.00,
    outputPrice: 75.00,
    reasoningDepth: "high",
    instructionFollowing: "high",
    codeGeneration: "high",
    latencyTier: "high",
    description: "Anthropic 최고 성능 모델. 복잡한 분석·연구·장문 작성 특화.",
  },
  {
    id: "claude-sonnet-4-6",
    label: "Claude 4.6 Sonnet",
    provider: "Anthropic",
    family: "Claude 4",
    version: "4.6 Sonnet",
    endpoint: ANTHROPIC_ENDPOINT,
    contextWindow: 200000,
    maxOutputTokens: 16000,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: true,
    inputPrice: 3.00,
    outputPrice: 15.00,
    reasoningDepth: "high",
    instructionFollowing: "high",
    codeGeneration: "high",
    latencyTier: "medium",
    description: "성능과 속도의 최적 균형. 에이전트·코딩 작업에 탁월.",
  },
  {
    id: "claude-haiku-4-5",
    label: "Claude 4.5 Haiku",
    provider: "Anthropic",
    family: "Claude 4",
    version: "4.5 Haiku",
    endpoint: ANTHROPIC_ENDPOINT,
    contextWindow: 200000,
    maxOutputTokens: 8192,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: true,
    inputPrice: 0.80,
    outputPrice: 4.00,
    reasoningDepth: "medium",
    instructionFollowing: "high",
    codeGeneration: "medium",
    latencyTier: "low",
    description: "Anthropic 최고속 경량 모델. 실시간 응답·대용량 처리에 적합.",
  },
];

// ── Google ────────────────────────────────────────────────────────────────────

const GOOGLE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai";

const GOOGLE_MODELS: ModelPreset[] = [
  {
    id: "gemini-3.1-pro-preview",
    label: "Gemini 3.1 Pro (Preview)",
    provider: "Google",
    family: "Gemini 3",
    version: "3.1 Pro",
    endpoint: GOOGLE_ENDPOINT,
    contextWindow: 1000000,
    maxOutputTokens: 65536,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: true,
    inputPrice: 1.25,
    outputPrice: 10.00,
    reasoningDepth: "high",
    instructionFollowing: "high",
    codeGeneration: "high",
    latencyTier: "medium",
    description: "Google 최신 플래그십 모델. 복잡한 추론 및 에이전트 작업 최적화.",
  },
  {
    id: "gemini-3-flash-preview",
    label: "Gemini 3 Flash (Preview)",
    provider: "Google",
    family: "Gemini 3",
    version: "3 Flash",
    endpoint: GOOGLE_ENDPOINT,
    contextWindow: 1000000,
    maxOutputTokens: 8192,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: true,
    inputPrice: 0.10,
    outputPrice: 0.40,
    reasoningDepth: "medium",
    instructionFollowing: "high",
    codeGeneration: "medium",
    latencyTier: "low",
    description: "초고속 프로덕션 모델. 높은 성능과 빠른 응답 속도의 조화.",
  },
];

// ── 전체 카탈로그 ──────────────────────────────────────────────────────────────

export const MODEL_CATALOG: ModelPreset[] = [
  ...OPENAI_MODELS,
  ...ANTHROPIC_MODELS,
  ...GOOGLE_MODELS,
];

export const MODEL_CATALOG_BY_PROVIDER: Record<string, ModelPreset[]> = {
  OpenAI:    OPENAI_MODELS,
  Anthropic: ANTHROPIC_MODELS,
  Google:    GOOGLE_MODELS,
};

/** 모델 ID로 프리셋 찾기 */
export function findPreset(id: string): ModelPreset | undefined {
  return MODEL_CATALOG.find(m => m.id === id);
}
