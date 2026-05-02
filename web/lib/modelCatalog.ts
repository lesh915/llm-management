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
    id: "claude-3-5-sonnet-20241022",
    label: "Claude 3.5 Sonnet",
    provider: "Anthropic",
    family: "Claude 3",
    version: "3.5 Sonnet",
    endpoint: ANTHROPIC_ENDPOINT,
    contextWindow: 200000,
    maxOutputTokens: 8192,
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
    id: "claude-3-5-haiku-20241022",
    label: "Claude 3.5 Haiku",
    provider: "Anthropic",
    family: "Claude 3",
    version: "3.5 Haiku",
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
  {
    id: "claude-3-opus-20240229",
    label: "Claude 3 Opus",
    provider: "Anthropic",
    family: "Claude 3",
    version: "3 Opus",
    endpoint: ANTHROPIC_ENDPOINT,
    contextWindow: 200000,
    maxOutputTokens: 4096,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: false,
    inputPrice: 15.00,
    outputPrice: 75.00,
    reasoningDepth: "high",
    instructionFollowing: "high",
    codeGeneration: "high",
    latencyTier: "high",
    description: "Claude 3 세대 플래그십. 고난도 태스크에 강점.",
  },
];

// ── Google ────────────────────────────────────────────────────────────────────

const GOOGLE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai";

const GOOGLE_MODELS: ModelPreset[] = [
  {
    id: "gemini-2.0-flash",
    label: "Gemini 2.0 Flash",
    provider: "Google",
    family: "Gemini 2",
    version: "2.0 Flash",
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
    description: "멀티모달 초고속 모델. 오디오·이미지·비디오 처리 지원.",
  },
  {
    id: "gemini-1.5-pro",
    label: "Gemini 1.5 Pro",
    provider: "Google",
    family: "Gemini 1",
    version: "1.5 Pro",
    endpoint: GOOGLE_ENDPOINT,
    contextWindow: 2000000,
    maxOutputTokens: 8192,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: false,
    inputPrice: 1.25,
    outputPrice: 5.00,
    reasoningDepth: "high",
    instructionFollowing: "high",
    codeGeneration: "high",
    latencyTier: "medium",
    description: "200만 토큰 컨텍스트 지원. 장문 문서·코드 분석에 탁월.",
  },
  {
    id: "gemini-1.5-flash",
    label: "Gemini 1.5 Flash",
    provider: "Google",
    family: "Gemini 1",
    version: "1.5 Flash",
    endpoint: GOOGLE_ENDPOINT,
    contextWindow: 1000000,
    maxOutputTokens: 8192,
    vision: true,
    toolUse: true,
    streaming: true,
    structuredOutput: false,
    inputPrice: 0.075,
    outputPrice: 0.30,
    reasoningDepth: "medium",
    instructionFollowing: "medium",
    codeGeneration: "medium",
    latencyTier: "low",
    description: "빠르고 저렴한 Gemini 경량 버전. 대용량 배치 처리에 적합.",
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
