export interface StreamCallbacks {
  onText: (text: string) => Promise<void>;
  onToolStart: (toolName: string, toolInput: Record<string, unknown>) => Promise<void>;
  onToolEnd: (toolName: string) => Promise<void>;
  onError: (error: Error) => Promise<void>;
}

export interface SessionInfo {
  sessionId: string;
  projectDir: string;
}
